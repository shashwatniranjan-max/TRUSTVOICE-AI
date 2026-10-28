"""Context anomaly checks: identity, destination, action fit, channel."""

from __future__ import annotations

from models.entities import entity_map
from models.intent import clean_text

SENSITIVE_INTENTS = {
    "credential_request",
    "financial_request",
    "sensitive_data_request",
    "personal_information_request",
}


def analyse_context(
    text: str,
    intent: str,
    identity_status: str,
    entities: list,
    conversation_state: dict | None = None,
) -> dict:
    clean = clean_text(text).lower()
    grouped = entity_map(entities)
    signals = []
    notes = []
    penalty = 0
    state = conversation_state or {}

    personal_channel = any(
        p in clean for p in (
            "personal email", "personal gmail", "personal account",
            "new bank account",
        )
    )
    email_destination = bool(grouped.get("EMAIL")) and any(
        v in clean for v in ("send", "mail", "forward", "export")
    )
    off_channel = personal_channel or email_destination
    direct_to_caller = any(
        p in clean for p in (
            "send me", "pay me", "transfer to me", "wire to me",
            "send to me", "to fix it", "gift card", "crypto", "bitcoin",
        )
    )
    new_account = (
        "new account" in clean
        or "different account" in clean
        or "new bank account" in clean
        or (intent == "financial_request" and "this account" in clean)
        or (intent == "financial_request" and direct_to_caller)
    )
    sensitive_doc = bool(grouped.get("DOCUMENT")) and any(
        x in clean for x in ("database", "kyc", "salary", "payroll", "confidential")
    )
    financial = intent == "financial_request"
    credential = intent == "credential_request"
    authority = (
        bool(grouped.get("PERSON_ROLE"))
        or "calling from" in clean
        or any(x in clean for x in ("from microsoft", "from apple", "from google", "from amazon", "tech support", "apple support", "microsoft support", "police"))
    )

    prior_intents = state.get("intents") or []
    prior_sensitive = any(i in SENSITIVE_INTENTS for i in prior_intents[-3:])

    if identity_status in {"UNVERIFIED", "NOT_AVAILABLE"} and not (
        intent in SENSITIVE_INTENTS or financial or credential
    ):
        notes.append(
            "Identity has not been independently established — that is not by itself malicious"
        )

    if identity_status == "UNVERIFIED" and authority:
        penalty += 8
        signals.append("unverified_authority")
        notes.append("Authority claim without independently established identity")

    if identity_status == "MISMATCH":
        penalty += 35
        signals.append("identity_mismatch")
        notes.append("Claimed identity does not match enrolled speaker evidence")

    if off_channel and (intent == "sensitive_data_request" or sensitive_doc):
        penalty += 28
        signals.append("off_channel_sensitive_data")
        notes.append("Sensitive data requested over an unusual / personal channel")

    if identity_status == "VERIFIED" and off_channel and (
        intent == "sensitive_data_request" or sensitive_doc
    ):
        penalty += 18
        signals.append("verified_but_unauthorized_channel")
        notes.append("Verified identity does not authorise off-channel data transfer")

    if financial and (new_account or off_channel):
        penalty += 22
        signals.append("new_payment_destination")
        notes.append("Financial transfer toward a new or unusual destination")

    if credential and identity_status in {"UNVERIFIED", "NOT_AVAILABLE", "MISMATCH"}:
        penalty += 16
        signals.append("credential_from_unverified")
        notes.append("Live credential request while identity is not independently established")

    if prior_sensitive and intent in SENSITIVE_INTENTS:
        penalty += 8
        signals.append("escalating_sensitive_requests")
        notes.append("Sensitive requests are accumulating across the conversation")

    # Benign workplace ask
    if intent in {"normal_conversation", "security_support"} and not off_channel and not credential:
        notes.append("No contextual anomaly detected")

    safety = int(max(4, min(96, 93 - penalty)))
    if safety >= 80:
        level = "NORMAL"
    elif safety >= 55:
        level = "UNUSUAL"
    else:
        level = "ANOMALY"

    # Structured context assessment audit
    auth_status = "AUTHORIZED" if (identity_status == "VERIFIED" and not off_channel) else (
        "PROHIBITED_CHANNEL" if (identity_status == "VERIFIED" and off_channel) else (
            "BIOMETRIC_MISMATCH" if identity_status == "MISMATCH" else "UNVERIFIED_AUTHORITY"
        )
    )

    context_audit = {
        "identity_status": identity_status,
        "is_sensitive_request": (intent in SENSITIVE_INTENTS or sensitive_doc),
        "is_unusual_destination": bool(new_account or off_channel),
        "is_off_channel": bool(off_channel),
        "authorization_status": auth_status,
        "channel_type": "Personal / External Channel" if off_channel else "Standard In-Band Channel",
        "prior_turns_count": len(prior_intents),
        "escalating_history": bool(prior_sensitive),
    }

    return {
        "Context Safety": safety,
        "context_level": level,
        "signals": signals,
        "notes": notes,
        "off_channel": off_channel,
        "new_destination": new_account or off_channel,
        "audit": context_audit,
    }
