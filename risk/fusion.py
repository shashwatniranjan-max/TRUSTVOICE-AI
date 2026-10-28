"""Transparent Dynamic Trust Score fusion and hard safety gates."""

from __future__ import annotations

from risk.config import FUSION_WEIGHTS, IDENTITY_SAFETY, TRUST_BANDS, VOICE_SAFETY


def voice_safety_from_label(label: str) -> int:
    return int(VOICE_SAFETY.get(label, VOICE_SAFETY["UNAVAILABLE"]))


def identity_safety_from_status(status: str) -> int:
    return int(IDENTITY_SAFETY.get(status, IDENTITY_SAFETY["NOT_AVAILABLE"]))


def compute_fused_score(components: dict) -> int:
    total = 0.0
    for key, weight in FUSION_WEIGHTS.items():
        total += float(components.get(key, 80)) * weight
    return int(round(total))


def trust_band(score: int) -> tuple[str, str]:
    for cutoff, risk, action in TRUST_BANDS:
        if score >= cutoff:
            return risk, action
    return "CRITICAL", "CRITICAL INTERVENTION"


SAFETY_GATE_SPECS = [
    {
        "id": "GATE_CRED_PRESSURE_UNVERIFIED",
        "name": "Live Credential Solicitation under High Pressure",
        "category": "Credential Security",
        "cap": 22,
        "forced_risk": "CRITICAL",
        "rationale": "Direct OTP, PIN, or password extraction under urgency from an unverified caller indicates an active account takeover attempt.",
        "condition_desc": "intent=credential_request AND (>=2 pressure cues OR threat) AND unverified identity",
    },
    {
        "id": "GATE_CRED_ELEVATED_CONTEXT",
        "name": "Live Credential Solicitation with Elevated Context",
        "category": "Credential Security",
        "cap": 38,
        "forced_risk": "HIGH",
        "rationale": "Live credential solicitation accompanied by pressure or unverified caller signals warrants immediate intervention.",
        "condition_desc": "intent=credential_request AND (pressure present OR credential_from_unverified signal)",
    },
    {
        "id": "GATE_CRED_DIRECT",
        "name": "Direct Credential Solicitation",
        "category": "Credential Security",
        "cap": 48,
        "forced_risk": "HIGH",
        "rationale": "Soliciting passwords, OTPs, or authentication codes directly is high-risk under any conversational pretext.",
        "condition_desc": "intent=credential_request",
    },
    {
        "id": "GATE_FINANCIAL_NEW_DEST_PRESSURE",
        "name": "Financial Transfer to New Destination under Pressure",
        "category": "Financial Security",
        "cap": 28,
        "forced_risk": "CRITICAL",
        "rationale": "Rerouting funds toward an unfamiliar destination under urgent deadlines is the primary vector for wire transfer fraud.",
        "condition_desc": "intent=financial_request AND new_destination AND (urgency OR artificial_deadline)",
    },
    {
        "id": "GATE_FINANCIAL_NEW_DEST",
        "name": "Financial Transfer toward New / Unusual Destination",
        "category": "Financial Security",
        "cap": 40,
        "forced_risk": "HIGH",
        "rationale": "Transfers toward newly introduced or unfamiliar account destinations require independent out-of-band confirmation.",
        "condition_desc": "intent=financial_request AND new_destination",
    },
    {
        "id": "GATE_SENSITIVE_OFF_CHANNEL_PRESSURE",
        "name": "Sensitive Data Exfiltration via Personal / Off-Channel Path",
        "category": "Data Exfiltration",
        "cap": 24,
        "forced_risk": "CRITICAL",
        "rationale": "Requesting proprietary databases or confidential records over personal channels under secrecy or claimed authority.",
        "condition_desc": "intent=sensitive_data_request AND off_channel AND (secrecy OR urgency OR identity=VERIFIED)",
    },
    {
        "id": "GATE_SENSITIVE_CONTEXT_CONCERN",
        "name": "Sensitive Data Request with Contextual Concern",
        "category": "Data Exfiltration",
        "cap": 36,
        "forced_risk": "HIGH",
        "rationale": "Sensitive dataset transmission requested alongside unusual channels or pressure tactics.",
        "condition_desc": "intent=sensitive_data_request AND (off_channel OR pressure present)",
    },
    {
        "id": "GATE_PERSONAL_UNVERIFIED_PRESSURE",
        "name": "Personal Data Request from Unverified Party under Pressure",
        "category": "Privacy Protection",
        "cap": 40,
        "forced_risk": "HIGH",
        "rationale": "Harvesting personal identity information under coercive time constraints.",
        "condition_desc": "intent=personal_information_request AND unverified identity AND pressure present",
    },
    {
        "id": "GATE_SPOOF_SENSITIVE_ACTION",
        "name": "Synthetic Voice Combined with High-Sensitivity Request",
        "category": "Deepfake Voice Exploit",
        "cap": 18,
        "forced_risk": "CRITICAL",
        "rationale": "AASIST synthetic voice detection paired with sensitive operational requests is high-probability deepfake fraud.",
        "condition_desc": "voice_label=LIKELY_SPOOF AND sensitive intent (credential/financial/sensitive_data)",
    },
    {
        "id": "GATE_SPEAKER_MISMATCH_SENSITIVE",
        "name": "Speaker Biometric Mismatch with High-Sensitivity Request",
        "category": "Impersonation Exploit",
        "cap": 20,
        "forced_risk": "CRITICAL",
        "rationale": "Caller claims a registered identity that fails voiceprint biometric verification while demanding sensitive access.",
        "condition_desc": "identity_status=MISMATCH AND sensitive intent",
    },
]


def evaluate_safety_gates_detailed(
    score: int, evidence: dict
) -> tuple[int, list[str], str | None, list[dict]]:
    """
    Evaluate all safety gates, returning the capped score, human-readable caps,
    the forced risk band (if any), and full audit records for every gate.
    """
    caps = []
    forced_risk = None
    intent = evidence.get("intent")
    behaviour_signals = set(evidence.get("behaviour_signals") or [])
    context_signals = set(evidence.get("context_signals") or [])
    identity = evidence.get("identity_status") or "NOT_AVAILABLE"
    voice = evidence.get("voice_label") or "UNAVAILABLE"
    pressure = behaviour_signals & {
        "urgency", "threat", "secrecy", "isolation",
        "verification_bypass", "artificial_deadline",
    }

    credential = intent == "credential_request"
    financial = intent == "financial_request"
    sensitive = intent == "sensitive_data_request"
    personal = intent == "personal_information_request"

    high_pressure = len(pressure) >= 2 or "threat" in pressure
    unverified = identity in {"UNVERIFIED", "NOT_AVAILABLE", "MISMATCH"}

    gates_evaluated = []
    current_score = int(score)

    for spec in SAFETY_GATE_SPECS:
        gid = spec["id"]
        triggered = False
        cap_val = spec["cap"]
        f_risk = spec["forced_risk"]

        if gid == "GATE_CRED_PRESSURE_UNVERIFIED":
            if credential and high_pressure and unverified:
                triggered = True
        elif gid == "GATE_CRED_ELEVATED_CONTEXT":
            if credential and (pressure or "credential_from_unverified" in context_signals):
                triggered = True
        elif gid == "GATE_CRED_DIRECT":
            if credential:
                triggered = True
        elif gid == "GATE_FINANCIAL_NEW_DEST_PRESSURE":
            if financial and evidence.get("new_destination") and (
                "urgency" in pressure or "artificial_deadline" in pressure
            ):
                triggered = True
        elif gid == "GATE_FINANCIAL_NEW_DEST":
            if financial and evidence.get("new_destination"):
                triggered = True
        elif gid == "GATE_SENSITIVE_OFF_CHANNEL_PRESSURE":
            if sensitive and evidence.get("off_channel") and (
                "secrecy" in pressure or "urgency" in pressure or identity == "VERIFIED"
            ):
                triggered = True
        elif gid == "GATE_SENSITIVE_CONTEXT_CONCERN":
            if sensitive and (evidence.get("off_channel") or pressure):
                triggered = True
        elif gid == "GATE_PERSONAL_UNVERIFIED_PRESSURE":
            if personal and unverified and pressure:
                triggered = True
        elif gid == "GATE_SPOOF_SENSITIVE_ACTION":
            if voice == "LIKELY_SPOOF" and intent in {
                "credential_request", "financial_request", "sensitive_data_request",
            }:
                triggered = True
        elif gid == "GATE_SPEAKER_MISMATCH_SENSITIVE":
            if identity == "MISMATCH" and intent in {
                "credential_request", "financial_request", "sensitive_data_request",
            }:
                triggered = True

        gate_record = dict(spec)
        gate_record["triggered"] = triggered
        if triggered:
            pre_cap = current_score
            if current_score > cap_val:
                current_score = cap_val
                gate_record["effect"] = f"Capped score from {pre_cap} to {cap_val} ({cap_val - pre_cap:+d} pts)"
            else:
                gate_record["effect"] = f"Maintained score cap at {cap_val} (score {pre_cap} was already below cap)"

            if f_risk:
                forced_risk = f_risk if (f_risk == "CRITICAL" or not forced_risk) else forced_risk
                gate_record["effect"] += f", enforced risk '{forced_risk}'"

            if gid == "GATE_CRED_PRESSURE_UNVERIFIED":
                caps.append("Credential request + pressure + unverified identity")
            elif gid == "GATE_CRED_ELEVATED_CONTEXT" and not any("Credential request + pressure" in c for c in caps):
                caps.append("Live credential solicitation with elevated context")
            elif gid == "GATE_CRED_DIRECT" and not caps:
                caps.append("Direct credential solicitation")
            elif gid == "GATE_FINANCIAL_NEW_DEST_PRESSURE":
                caps.append("Financial transfer to a new destination under time pressure")
            elif gid == "GATE_FINANCIAL_NEW_DEST" and not any("Financial transfer" in c for c in caps):
                caps.append("Financial transfer toward a new or unusual destination")
            elif gid == "GATE_SENSITIVE_OFF_CHANNEL_PRESSURE":
                caps.append("Sensitive data + unusual destination + pressure or over-claim of authority")
            elif gid == "GATE_SENSITIVE_CONTEXT_CONCERN" and not any("Sensitive data" in c for c in caps):
                caps.append("Sensitive data request with contextual concern")
            elif gid == "GATE_PERSONAL_UNVERIFIED_PRESSURE":
                caps.append("Personal data request from an unverified party under pressure")
            elif gid == "GATE_SPOOF_SENSITIVE_ACTION":
                caps.append("Likely synthetic voice combined with a high-sensitivity request")
            elif gid == "GATE_SPEAKER_MISMATCH_SENSITIVE":
                caps.append("Speaker mismatch with a high-sensitivity request")
        else:
            gate_record["effect"] = "Conditions not met (gate inactive)"

        gates_evaluated.append(gate_record)

    seen = set()
    deduped_caps = []
    for c in caps:
        if c not in seen:
            seen.add(c)
            deduped_caps.append(c)

    return current_score, deduped_caps, forced_risk, gates_evaluated


def apply_safety_gates(score: int, evidence: dict) -> tuple[int, list[str], str | None]:
    """
    Caps require combinations. A single keyword or an inconclusive voice
    signal is not enough to collapse the score.
    """
    capped_score, caps, forced_risk, _ = evaluate_safety_gates_detailed(score, evidence)
    return capped_score, caps, forced_risk


def explain_fusion_calculation(
    components: dict,
    preliminary_score: int,
    final_score: int,
    gates_evaluated: list[dict],
    forced_risk: str | None = None,
) -> dict:
    """Produce an exact mathematical breakdown of the 5-dimension risk fusion calculation."""
    dimension_names = {
        "voice_authenticity": "Voice Authenticity",
        "speaker_identity": "Speaker Identity",
        "intent_safety": "Intent Safety",
        "behaviour_safety": "Behavioural Safety",
        "context_safety": "Contextual Safety",
    }
    dimensions = {}
    sum_weighted = 0.0

    for key, weight in FUSION_WEIGHTS.items():
        raw = float(components.get(key, 80))
        pts = round(raw * weight, 2)
        sum_weighted += pts

        if raw >= 80:
            rating = "Safe / Normal"
        elif raw >= 55:
            rating = "Review / Caution"
        else:
            rating = "Critical Risk"

        dimensions[key] = {
            "key": key,
            "label": dimension_names.get(key, key.replace("_", " ").title()),
            "weight": weight,
            "weight_pct": f"{int(round(weight * 100))}%",
            "raw_score": int(round(raw)),
            "weighted_points": pts,
            "rating": rating,
        }

    triggered = [g for g in gates_evaluated if g.get("triggered")]
    delta = final_score - preliminary_score
    gate_modified = (delta != 0) or (forced_risk is not None)

    return {
        "dimensions": dimensions,
        "preliminary_score": preliminary_score,
        "preliminary_exact": round(sum_weighted, 2),
        "final_score": final_score,
        "delta": delta,
        "gate_modified": gate_modified,
        "forced_risk": forced_risk,
        "gates_evaluated": gates_evaluated,
        "gates_triggered": triggered,
        "active_gate_count": len(triggered),
        "total_gates_count": len(gates_evaluated),
        "formula_display": "Trust Score = (15% × Voice) + (10% × Identity) + (30% × Intent) + (25% × Behaviour) + (20% × Context)",
    }


def recommended_action(
    interaction_risk: str,
    voice_label: str,
    identity_status: str,
) -> tuple[str, str]:
    """Return (action code, human explanation)."""
    if interaction_risk == "CRITICAL":
        return (
            "CRITICAL INTERVENTION",
            "Independent verification is required. Voice identity alone is not sufficient authorization for this action.",
        )
    if interaction_risk == "HIGH":
        return (
            "VERIFY",
            "Hold the sensitive action and verify through a trusted channel or device.",
        )
    if interaction_risk == "ELEVATED":
        return (
            "WARN",
            "Continue with caution. Confirm unusual details before sharing information or moving funds.",
        )

    if voice_label == "LIKELY_SPOOF":
        return (
            "WARN",
            "Interaction content looks ordinary, but the voice authenticity signal is weak. Review the voice independently if identity matters.",
        )
    if voice_label in {"INCONCLUSIVE", "INCONCLUSIVE_QUALITY"}:
        extra = " Continue the conversation, but use an independent check if identity matters."
        if identity_status in {"UNVERIFIED", "NOT_AVAILABLE"}:
            extra = " Identity has not been independently established."
        return (
            "CONTINUE",
            "Interaction risk is low. Voice authenticity is inconclusive — not a reason to treat the conversation as an attack."
            + extra,
        )
    return (
        "CONTINUE",
        "No sensitive request or social-engineering combination detected.",
    )


def authenticity_display(label: str, evidence_kind: str = "", source: str = "") -> str:
    base = {
        "LIKELY_AUTHENTIC": "LIKELY AUTHENTIC",
        "LIKELY_SPOOF": "LIKELY SPOOF",
        "INCONCLUSIVE": "INCONCLUSIVE",
        "INCONCLUSIVE_QUALITY": "INCONCLUSIVE / AUDIO QUALITY",
        "UNAVAILABLE": "UNAVAILABLE",
    }.get(label, label.replace("_", " "))
    demo = source == "DEMO SCENARIO" or evidence_kind == "illustrative"
    if demo and label != "UNAVAILABLE":
        return f"{base} (illustrative demo input — not a live model verdict)"
    if evidence_kind == "model":
        return f"{base} (model-derived countermeasure score — not a calibrated probability)"
    return base
