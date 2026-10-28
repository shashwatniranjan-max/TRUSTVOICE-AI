"""Lightweight regex entity extraction for the prototype risk layer."""

from __future__ import annotations

import re

from models.intent import clean_text

ENTITY_SPECS = [
    (
        "AMOUNT",
        re.compile(
            r"(?:[\$₹€£]\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?|"
            r"[\$₹€£]\s*\d+(?:\.\d+)?|"
            r"(?:rs\.?|inr|usd|eur|gbp)\s*\d{1,3}(?:,\d{2,3})*(?:\.\d+)?|"
            r"(?:rs\.?|inr|usd|eur|gbp)\s*\d+(?:\.\d+)?|"
            r"\b\d{1,3}(?:,\d{2,3})*(?:\.\d+)?\s*(?:rupees?|rs\.?|inr|dollars?|usd|bucks|euros?|pounds?)\b|"
            r"\b\d{3,}\s*(?:rupees?|rs\.?|inr|dollars?|usd|bucks|euros?|pounds?)\b|"
            r"\b(?:thirty|fifty|twenty|forty|ten|two|one|five|hundred)\s+(?:thousand|million|lakh|lac)\s*(?:rupees?|dollars?|usd)?\b)",
            re.I,
        ),
    ),
    (
        "ACCOUNT",
        re.compile(
            r"\b(?:account(?:\s+number)?|a/c)\s*[:#-]?\s*(\d{6,18})\b|"
            r"\b(personal account|new bank account)\b",
            re.I,
        ),
    ),
    (
        "OTP",
        re.compile(r"\b(?:otp|one[- ]time password|verification code)\b", re.I),
    ),
    (
        "PHONE",
        re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b"),
    ),
    (
        "EMAIL",
        re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    ),
    (
        "BANK",
        re.compile(
            r"\b(?:your bank|the bank|bank security(?: team)?|sbi|hdfc|icici|axis bank|kotak)\b",
            re.I,
        ),
    ),
    (
        "PAYMENT_METHOD",
        re.compile(r"\b(?:upi|neft|imps|rtgs|gift cards?|crypto|bitcoin|wallet)\b", re.I),
    ),
    (
        "DESTINATION",
        re.compile(
            r"\b(?:personal (?:email|gmail|number|account)|gmail|"
            r"new (?:bank )?account|different account|this account|"
            r"send (?:to )?me|pay (?:to )?me|transfer to me|my wallet|my address)\b",
            re.I,
        ),
    ),
    (
        "DOCUMENT",
        re.compile(
            r"\b(?:employee database|customer (?:database|records|kyc)|salary (?:sheet|data)|"
            r"payroll|kyc documents?|kyc|attendance report|confidential files?|"
            r"client contact list|audit report)\b",
            re.I,
        ),
    ),
    (
        "PERSON_ROLE",
        re.compile(
            r"\b(?:your manager|i am (?:your )?manager|\bmanager\b|"
            r"from (?:your )?bank|security (?:department|team)|bank security team|"
            r"\bceo\b|\bhr\b|fraud team|"
            r"from\s+(?:microsoft|apple|google|amazon|windows|tech support|it support|help desk|support team|service center|the police|police|cbi|fbi|irs)|"
            r"(?:tech support|it support|help desk|support agent|technician|system administrator)|"
            r"(?:apple|microsoft|google|amazon)\s+(?:support|security|team))\b",
            re.I,
        ),
    ),
]

ENTITY_CATEGORIES = {
    "OTP": ("OTPs & Credential References", "CRITICAL"),
    "ACCOUNT": ("Account References", "HIGH"),
    "AMOUNT": ("Monetary Amounts", "ELEVATED"),
    "PHONE": ("Phone Numbers", "INFORMATIONAL"),
    "EMAIL": ("Email Addresses", "INFORMATIONAL"),
    "BANK": ("Banks", "INFORMATIONAL"),
    "PAYMENT_METHOD": ("Payment Methods", "ELEVATED"),
    "DESTINATION": ("Payment & Transfer Destinations", "HIGH"),
    "DOCUMENT": ("Sensitive Documents & Databases", "HIGH"),
    "PERSON_ROLE": ("Roles & Identity References", "INFORMATIONAL"),
}


def redact_entity_value(label: str, value: str) -> str:
    """Mask sensitive PII values for safe display in UI and exported reports."""
    val = str(value).strip()
    if label == "OTP":
        return "[REDACTED OTP]"
    if label == "ACCOUNT":
        digits = re.sub(r"\D", "", val)
        if len(digits) >= 4:
            return f"******{digits[-4:]}"
        return "[REDACTED ACCOUNT]"
    if label == "PHONE":
        digits = re.sub(r"\D", "", val)
        if len(digits) >= 6:
            return f"+91 {digits[:2]}******{digits[-2:]}"
        return "[REDACTED PHONE]"
    if label == "EMAIL":
        if "@" in val:
            user, domain = val.split("@", 1)
            masked_user = user[0] + "***" if len(user) > 1 else "***"
            return f"{masked_user}@{domain}"
        return "[REDACTED EMAIL]"
    return val


def extract_entities(text: str) -> list[dict]:
    clean = clean_text(text)
    if not clean:
        return []
    found = []
    seen = set()
    for label, pattern in ENTITY_SPECS:
        for match in pattern.finditer(clean):
            value = match.group(1) if match.lastindex else match.group(0)
            value = " ".join(str(value).split())
            key = (label, value.lower())
            if key in seen:
                continue
            seen.add(key)
            cat_name, risk_lvl = ENTITY_CATEGORIES.get(label, ("General", "INFORMATIONAL"))
            redacted = redact_entity_value(label, value)
            found.append({
                "type": label,
                "value": value,
                "redacted_value": redacted,
                "category": cat_name,
                "risk_relevance": risk_lvl,
                "matched_text": match.group(0),
            })
    return found


def entity_map(entities: list[dict]) -> dict:
    grouped = {}
    for item in entities:
        grouped.setdefault(item["type"], []).append(item["value"])
    return grouped


def categorized_entity_inventory(entities: list[dict]) -> dict:
    """Group extracted entities into the 8 canonical security categories with detection flags."""
    categories_spec = [
        ("OTP & Credential References", "OTP", "Direct authentication tokens, passcodes, or OTPs"),
        ("Account References", "ACCOUNT", "Bank account numbers or personal account mentions"),
        ("Monetary Amounts", "AMOUNT", "Financial values in INR or colloquial terms"),
        ("Phone Numbers & Email Addresses", ("PHONE", "EMAIL"), "Contact identifiers and electronic mail addresses"),
        ("Banks & Payment Methods", ("BANK", "PAYMENT_METHOD"), "Financial institutions, UPI, NEFT, IMPS, or crypto channels"),
        ("Payment Destinations", "DESTINATION", "Unusual routing destinations or off-channel transfers"),
        ("Sensitive Documents", "DOCUMENT", "Proprietary files, KYC records, or employee databases"),
        ("Roles & Authority References", "PERSON_ROLE", "Manager, bank executive, or security authority claims"),
    ]
    inventory = []
    for title, type_keys, desc in categories_spec:
        keys = (type_keys,) if isinstance(type_keys, str) else type_keys
        matched = [e for e in entities if e["type"] in keys]
        inventory.append({
            "title": title,
            "description": desc,
            "detected": len(matched) > 0,
            "count": len(matched),
            "items": matched,
            "highest_risk": max([e["risk_relevance"] for e in matched], key=lambda r: {"CRITICAL": 3, "HIGH": 2, "ELEVATED": 1, "INFORMATIONAL": 0}.get(r, 0)) if matched else "NONE",
        })
    return {
        "categories": inventory,
        "total_extracted": len(entities),
        "total_categories_active": sum(1 for c in inventory if c["detected"]),
    }
