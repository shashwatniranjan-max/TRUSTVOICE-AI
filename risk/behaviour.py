"""Observable social-engineering indicators. Combinations matter more than single cues."""

from __future__ import annotations

import re

from models.intent import clean_text

SENSITIVE_INTENTS = {
    "credential_request",
    "financial_request",
    "sensitive_data_request",
    "personal_information_request",
    "authorization_request",
}

CUES = [
    ("urgency", r"\b(immediately|right now|urgent(ly)?|hurry|quickly|at once|do it now|abhi|need to (?:send|pay|transfer)|have to (?:send|pay|transfer)|must (?:send|pay|transfer))\b", "Urgency", "Severe time contraction to bypass deliberative thought"),
    ("threat", r"\b(will be (?:blocked|suspended|closed|frozen|arrested)|permanently blocked|legal action|arrest(ed)?|you will lose|otherwise|(?:computer|pc|system|device|phone|laptop)\s+(?:has|got|infected with|compromised by)\s+(?:a\s+)?(?:virus|malware|trojan|ransomware|spyware)|(?:infected with|compromised by)\s+(?:a\s+)?(?:virus|malware|trojan|ransomware)|(?:your )?(?:computer|system|device)\s+has\s+(?:a\s+)?virus|(?:detected|found)\s+(?:a\s+)?(?:virus|malware|trojan|ransomware|spyware)|(?:virus|malware|trojan|ransomware)\s+on\s+(?:your\s+)?(?:computer|pc|phone|device|system|laptop))\b", "Threats & Consequences", "Punitive or alarming consequences to coerce compliance"),
    ("secrecy", r"\b(don't tell anyone|do not tell anyone|keep this secret|don't mention|no one should know|keep this between us)\b", "Secrecy & Concealment", "Attempts to hide the transaction or request from internal colleagues or family"),
    ("isolation", r"\b(don't hang up|do not hang up|don't disconnect|stay on the (line|call)|don't call (the )?bank)\b", "Caller Isolation", "Preventing the victim from contacting official support or external advisers"),
    ("verification_bypass", r"\b(trust me|no need to (verify|check|confirm)|skip the (verification|process)|don't mention this to anyone|don't verify)\b", "Verification Bypass", "Explicitly urging the target to disregard normal authentication safeguards"),
    ("authority_claim", r"\b(i am (?:calling from|your manager|from (?:your )?bank|the manager)|this is (?:your )?bank|security department|bank security|(?:calling from|from)\s+(?:microsoft|apple|google|amazon|windows|tech support|it support|help desk|support team|service center|the police|police|cbi|fbi|irs)|this is\s+[\w\s]{1,25}\s+from\s+(?:microsoft|apple|google|amazon|windows|tech support|it support|the bank|bank)|this is\s+(?:apple|microsoft|google|amazon|windows|bank)\s+(?:support|security|service|it))\b", "Authority Claim", "Invoking management hierarchy, executive status, or bank authority"),
    ("artificial_deadline", r"\b(last (chance|warning)|final notice|expires? (today|in)|in \d+ minutes?|before (evening|5 ?pm))\b", "Artificial Deadline", "Fabricating immediate expiration or deadline to rush execution"),
    ("soft_deadline", r"\b(today|by eod|this evening)\b", "Time Expectation", "Standard temporal expectation for request completion"),
]


def analyse_behaviour(text: str, intent: str = "normal_conversation") -> dict:
    clean = clean_text(text)
    signals = []
    labels = []
    matches = {}
    for key, pattern, label, _ in CUES:
        m = re.search(pattern, clean, flags=re.I)
        if m:
            signals.append(key)
            labels.append(label)
            matches[key] = m.group(0)

    if re.search(r"\bwhen you (have time|can)\b", clean, flags=re.I):
        signals = [s for s in signals if s not in {"soft_deadline", "urgency"}]
        labels = [lb for lb in labels if lb not in {"Time Expectation", "Urgency"}]
        matches.pop("soft_deadline", None)
        matches.pop("urgency", None)

    sensitive = intent in SENSITIVE_INTENTS
    penalty = 0
    notes = []
    indicator_audit = []

    # Calculate penalties per indicator
    for key, pattern, label, desc in CUES:
        is_detected = key in signals
        cue_penalty = 0
        cue_sev = "LOW"
        cue_exp = desc

        if key in ("urgency", "artificial_deadline"):
            if is_detected:
                if sensitive:
                    cue_penalty = 18
                    cue_sev = "CRITICAL" if key == "urgency" else "HIGH"
                    cue_exp = "Urgent pacing paired with a high-sensitivity request significantly lowers trust."
                else:
                    cue_penalty = 40
                    cue_sev = "MEDIUM"
                    cue_exp = "Strong urgency language detected without explicit sensitive payload."

        elif key == "soft_deadline":
            if is_detected and "urgency" not in signals:
                cue_penalty = 18
                cue_sev = "LOW"
                cue_exp = "Same-day deadline expectation noted."

        elif key == "threat":
            if is_detected:
                cue_penalty = 16 if sensitive else 8
                cue_sev = "CRITICAL" if sensitive else "HIGH"
                cue_exp = "Coercive threat/consequence language detected."

        elif key == "secrecy":
            if is_detected:
                cue_penalty = 20 if sensitive else 10
                cue_sev = "CRITICAL" if sensitive else "HIGH"
                cue_exp = "Caller demands concealment or secrecy, characteristic of social engineering."

        elif key == "isolation":
            if is_detected:
                cue_penalty = 14
                cue_sev = "HIGH"
                cue_exp = "Attempting to isolate the listener and prevent external confirmation."

        elif key == "verification_bypass":
            if is_detected:
                cue_penalty = 16 if sensitive else 8
                cue_sev = "CRITICAL" if sensitive else "HIGH"
                cue_exp = "Directly instructing target to bypass standard verification protocols."

        elif key == "authority_claim":
            if is_detected:
                cue_penalty = 10 if sensitive else 0
                cue_sev = "HIGH" if sensitive else "INFORMATIONAL"
                cue_exp = "Authority or executive standing claimed during conversation."

        penalty += cue_penalty
        indicator_audit.append({
            "key": key,
            "label": label,
            "detected": is_detected,
            "evidence": matches.get(key),
            "severity": cue_sev if is_detected else "NONE",
            "penalty": cue_penalty,
            "explanation": cue_exp,
        })

    # Summary notes matching legacy test expectations
    if "urgency" in signals or "artificial_deadline" in signals:
        if sensitive:
            notes.append("Urgency combined with a sensitive request")
        else:
            notes.append("Strong urgency language (not by itself a critical interaction)")

    if "soft_deadline" in signals and "urgency" not in signals:
        notes.append("Same-day time expectation")

    if "threat" in signals:
        notes.append("Threat / consequence language")

    if "secrecy" in signals:
        notes.append("Secrecy request")

    if "isolation" in signals:
        notes.append("Isolation attempt")

    if "verification_bypass" in signals:
        notes.append("Verification bypass language")

    if "authority_claim" in signals and sensitive:
        notes.append("Authority claim alongside a sensitive request")

    combo = len(signals)
    if combo >= 3 and sensitive:
        penalty += 12
        notes.append("Multiple social-engineering indicators combined")
    elif combo >= 3:
        penalty += 6
        notes.append("Multiple pressure indicators, request itself not sensitive")

    safety = int(max(4, min(96, 94 - penalty)))
    if safety >= 80:
        level = "LOW"
    elif safety >= 55:
        level = "MEDIUM"
    else:
        level = "HIGH"

    return {
        "Behaviour Safety": safety,
        "behaviour_level": level,
        "signals": signals,
        "signal_labels": labels,
        "notes": notes,
        "indicators": indicator_audit,
        "detected_count": len(signals),
        "total_indicators_evaluated": len(CUES),
        "disclaimer": "Observable social-engineering indicators detected."
        if signals else "No major social-engineering indicators observed.",
    }
