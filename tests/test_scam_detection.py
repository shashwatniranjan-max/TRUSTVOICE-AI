"""Tests for scam, tech support, extortion, and international currency detection."""

import pytest
from models.entities import extract_entities
from models.intent import classify_intent
from risk.behaviour import analyse_behaviour
from risk.context import analyse_context
from risk.pipeline import analyse_interaction


def test_tech_support_microsoft_virus_scam():
    text = "Hello, this is Sandhouse from Microsoft. Your computer has virus. You need to send me $30,000 to fix it."
    res = analyse_interaction(text)

    # 1. Intent should be financial_request
    assert res["intent"]["intent"] == "financial_request"

    # 2. Entities should extract the amount and role
    extracted = {e["type"]: e["value"] for e in res["entities"]}
    assert "AMOUNT" in extracted
    assert "$30,000" in extracted["AMOUNT"]
    assert "PERSON_ROLE" in extracted

    # 3. Behaviour cues should detect threat, authority claim, and urgency
    assert "threat" in res["behaviour_signals"]
    assert "authority_claim" in res["behaviour_signals"]
    assert "urgency" in res["behaviour_signals"]

    # 4. Critical safety gates should fire
    assert res["trust_score"] <= 25
    assert res["interaction_risk"] == "CRITICAL"
    assert res["action"] == "CRITICAL INTERVENTION"
    assert any("threat" in g.lower() or "financial" in g.lower() for g in res["gates"])


def test_police_arrest_extortion_scam():
    text = "I am calling from police department. You will be arrested. You must pay $2,000 immediately."
    res = analyse_interaction(text)

    assert res["intent"]["intent"] == "financial_request"
    assert "threat" in res["behaviour_signals"]
    assert "urgency" in res["behaviour_signals"]
    assert res["trust_score"] <= 25
    assert res["interaction_risk"] == "CRITICAL"


def test_apple_tech_support_scam():
    text = "This is Apple support. We detected malware on your phone. Transfer 500 dollars right now to clear it."
    res = analyse_interaction(text)

    assert res["intent"]["intent"] == "financial_request"
    assert res["interaction_risk"] in ("HIGH", "CRITICAL")
    assert res["trust_score"] <= 35


def test_benign_conversations_not_flagged_as_scams():
    # 1. Normal meeting
    res1 = analyse_interaction("Hey, are we still meeting at five o'clock?")
    assert res1["interaction_risk"] == "LOW"
    assert res1["trust_score"] >= 80

    # 2. Benign work document request
    res2 = analyse_interaction("Can you send me yesterday's meeting notes and the project presentation?")
    assert res2["interaction_risk"] == "LOW"
    assert res2["trust_score"] >= 80

    # 3. Security advice / warning
    res3 = analyse_interaction("Remember, legitimate bank agents will never ask for your OTP or password.")
    assert res3["intent"]["intent"] in ("security_support", "normal_conversation")
    assert res3["interaction_risk"] == "LOW"


def test_international_currencies_entity_extraction():
    e1 = extract_entities("Please pay $1,500.50 via card.")
    assert any(e["type"] == "AMOUNT" and "$1,500.50" in e["value"] for e in e1)

    e2 = extract_entities("Total cost is 2500 USD.")
    assert any(e["type"] == "AMOUNT" and "2500" in e["value"] for e in e2)

    e3 = extract_entities("Transfer €750 to the account.")
    assert any(e["type"] == "AMOUNT" and "€750" in e["value"] for e in e3)

    e4 = extract_entities("He demanded fifty thousand dollars.")
    assert any(e["type"] == "AMOUNT" and "fifty thousand dollars" in e["value"].lower() for e in e4)

    # Indian rupee backwards compatibility
    e5 = extract_entities("Transfer ₹50,000 to my account.")
    assert any(e["type"] == "AMOUNT" and "50,000" in e["value"] for e in e5)
