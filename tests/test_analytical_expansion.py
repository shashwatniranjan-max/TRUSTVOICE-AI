"""Unit tests for expanded analytical capabilities, mathematical fusion, safety gates, and reporting."""

import pytest
from models.entities import extract_entities, redact_entity_value, categorized_entity_inventory
from models.intent import classify_intent
from risk.behaviour import analyse_behaviour
from risk.context import analyse_context
from risk.config import FUSION_WEIGHTS
from risk.fusion import (
    compute_fused_score,
    evaluate_safety_gates_detailed,
    explain_fusion_calculation,
    SAFETY_GATE_SPECS,
)
from risk.pipeline import analyse_interaction
from utils.reporting import build_incident_report, build_incident_report_pdf, REPORTLAB_AVAILABLE
from utils.state import new_conversation_state, update_conversation_state


class TestMathematicalFusionAndGates:
    def test_fusion_weights_sum_to_one(self):
        total_weight = sum(FUSION_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 1e-6, "Fusion weights must sum to exactly 1.0"
        assert FUSION_WEIGHTS["voice_authenticity"] == 0.15
        assert FUSION_WEIGHTS["speaker_identity"] == 0.10
        assert FUSION_WEIGHTS["intent_safety"] == 0.30
        assert FUSION_WEIGHTS["behaviour_safety"] == 0.25
        assert FUSION_WEIGHTS["context_safety"] == 0.20

    def test_benign_conversation_fusion_math(self):
        components = {
            "voice_authenticity": 92,
            "speaker_identity": 72,
            "intent_safety": 96,
            "behaviour_safety": 94,
            "context_safety": 93,
        }
        # Expected: 92*0.15 (13.8) + 72*0.10 (7.2) + 96*0.30 (28.8) + 94*0.25 (23.5) + 93*0.20 (18.6) = 91.9 -> 92
        fused = compute_fused_score(components)
        assert fused == 92

        explanation = explain_fusion_calculation(components, fused, fused, [], None)
        assert explanation["preliminary_score"] == 92
        assert explanation["final_score"] == 92
        assert explanation["delta"] == 0
        assert explanation["gate_modified"] is False
        assert len(explanation["gates_triggered"]) == 0

    def test_hard_safety_gate_credential_theft_caps_score(self):
        # Credential theft with high pressure and unverified identity
        evidence = {
            "intent": "credential_request",
            "behaviour_signals": ["urgency", "threat"],
            "context_signals": ["credential_from_unverified"],
            "identity_status": "UNVERIFIED",
            "voice_label": "UNAVAILABLE",
        }
        preliminary_score = 85
        capped, caps, forced_risk, gates_eval = evaluate_safety_gates_detailed(preliminary_score, evidence)
        assert capped <= 22, "High pressure credential theft must cap score at 22"
        assert forced_risk == "CRITICAL"
        assert any("Credential request + pressure" in c for c in caps)

        # Audit check
        audit = explain_fusion_calculation({}, preliminary_score, capped, gates_eval, forced_risk)
        assert audit["gate_modified"] is True
        assert audit["delta"] == capped - preliminary_score
        assert len(audit["gates_triggered"]) >= 1

    def test_all_ten_safety_gates_catalogued(self):
        assert len(SAFETY_GATE_SPECS) == 10
        gate_ids = [g["id"] for g in SAFETY_GATE_SPECS]
        assert "GATE_CRED_PRESSURE_UNVERIFIED" in gate_ids
        assert "GATE_FINANCIAL_NEW_DEST_PRESSURE" in gate_ids
        assert "GATE_SENSITIVE_OFF_CHANNEL_PRESSURE" in gate_ids
        assert "GATE_SPOOF_SENSITIVE_ACTION" in gate_ids
        assert "GATE_SPEAKER_MISMATCH_SENSITIVE" in gate_ids


class TestEntityExtractionAndRedaction:
    def test_otp_redaction(self):
        assert redact_entity_value("OTP", "482195") == "[REDACTED OTP]"
        assert redact_entity_value("OTP", "1234") == "[REDACTED OTP]"

    def test_account_redaction(self):
        assert redact_entity_value("ACCOUNT", "123456789012") == "******9012"
        assert redact_entity_value("ACCOUNT", "987654321") == "******4321"

    def test_email_and_phone_redaction(self):
        masked_email = redact_entity_value("EMAIL", "rahul.sharma@example.com")
        assert masked_email.startswith("r***@")
        assert "example.com" in masked_email

        masked_phone = redact_entity_value("PHONE", "9876543210")
        assert masked_phone.startswith("+91 98")
        assert masked_phone.endswith("10")

    def test_categorized_entity_inventory(self):
        text = "Please send OTP 5928 to account 9876543210 and transfer ₹50,000 to user@gmail.com"
        entities = extract_entities(text)
        assert len(entities) >= 3

        cat_inv = categorized_entity_inventory(entities)
        assert cat_inv["total_extracted"] == len(entities)
        assert cat_inv["total_categories_active"] >= 3
        # Ensure OTP category detected
        otp_cat = next((c for c in cat_inv["categories"] if "OTP" in c["title"]), None)
        assert otp_cat is not None
        assert otp_cat["detected"] is True
        assert otp_cat["items"][0]["redacted_value"] == "[REDACTED OTP]"


class TestBehaviourAndContextDiagnostics:
    def test_behaviour_indicator_audit(self):
        text = "Transfer the money immediately right now or your account will be permanently blocked"
        res = analyse_behaviour(text, intent="financial_request")
        assert "urgency" in res["signals"]
        assert "threat" in res["signals"]
        assert len(res["indicators"]) == 8

        # Check that detected signals have evidence
        urgency_ind = next(i for i in res["indicators"] if i["key"] == "urgency")
        assert urgency_ind["detected"] is True
        assert urgency_ind["evidence"] is not None
        assert urgency_ind["penalty"] > 0

        # Absent indicator
        secrecy_ind = next(i for i in res["indicators"] if i["key"] == "secrecy")
        assert secrecy_ind["detected"] is False
        assert secrecy_ind["penalty"] == 0

    def test_context_off_channel_detection(self):
        text = "Send the employee database to my personal gmail immediately"
        entities = extract_entities(text)
        res = analyse_context(text, intent="sensitive_data_request", identity_status="UNVERIFIED", entities=entities)
        assert res["off_channel"] is True
        assert res["audit"]["is_off_channel"] is True
        assert res["audit"]["is_sensitive_request"] is True
        assert "off_channel_sensitive_data" in res["signals"]


class TestMultiTurnStateAndSignalsSummary:
    def test_multi_turn_progression_tracking(self):
        state = new_conversation_state()

        # Turn 1: Benign greeting
        t1 = analyse_interaction("Hello, how are you doing today?", conversation_state=state)
        state = t1["conversation_state"]
        assert len(state["turn_history"]) == 1
        assert state["turn_history"][0]["turn_index"] == 1
        assert state["turn_history"][0]["trust_score"] >= 80

        # Turn 2: Urgent sensitive request
        t2 = analyse_interaction(
            "I need the employee database sent to my personal email right now",
            conversation_state=state,
        )
        state = t2["conversation_state"]
        assert len(state["turn_history"]) == 2
        assert state["turn_history"][1]["turn_index"] == 2
        assert state["turn_history"][1]["trust_score"] < state["turn_history"][0]["trust_score"]
        assert state["turn_history"][1]["score_change"] < 0
        assert state["first_high_risk_turn"] == 2 or state["first_critical_risk_turn"] == 2

    def test_signals_summary_in_interaction(self):
        res = analyse_interaction("Give me the OTP immediately or your account will be blocked")
        signals = res.get("signals_summary", {})
        assert signals["total_signals_recorded"] > 0
        assert signals["active_threats_count"] >= 2
        assert signals["high_severity_count"] >= 1
        assert len(signals["dimensions_affected"]) > 0


class TestIncidentReporting:
    def test_json_and_pdf_report_generation(self):
        analysed = analyse_interaction("Please transfer ₹25,000 to new account 987654321 immediately")
        session = {
            "last_result": analysed,
            "analysis_source": "TEST_SUITE",
            "score": analysed["trust_score"],
            "conversation_state": analysed["conversation_state"],
        }
        report_dict = build_incident_report(session)
        assert report_dict["report_id"].startswith("TV-")
        assert report_dict["trust_score"] == analysed["trust_score"]
        assert "fusion_audit" in report_dict
        assert "signals_summary" in report_dict
        assert "categorized_entities" in report_dict

        if REPORTLAB_AVAILABLE:
            pdf_bytes = build_incident_report_pdf(report_dict)
            assert isinstance(pdf_bytes, bytes)
            assert len(pdf_bytes) > 1000
            assert pdf_bytes.startswith(b"%PDF")
