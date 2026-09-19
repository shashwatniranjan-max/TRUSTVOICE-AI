"""Deterministic behavioural tests for the TRUSTVOICE prototype pipeline."""

import unittest

import numpy as np

from models.antispoof import derive_verdict
from models.entities import extract_entities
from models.intent import classify_intent
from risk.pipeline import analyse_interaction
from utils.audio import quality_gate
from utils.state import new_conversation_state


class PipelineAcceptanceTests(unittest.TestCase):
    def test_benign_meeting(self):
        r = analyse_interaction("Hey, are we still meeting at five?")
        self.assertEqual(r["intent"]["intent"], "normal_conversation")
        self.assertEqual(r["behaviour"]["behaviour_level"], "LOW")
        self.assertEqual(r["context"]["context_level"], "NORMAL")
        self.assertEqual(r["interaction_risk"], "LOW")
        self.assertNotEqual(r["action"], "CRITICAL INTERVENTION")
        self.assertFalse(r["handshake_required"])

    def test_security_advice_otp(self):
        r = analyse_interaction("The bank will never ask you for your OTP.")
        self.assertNotEqual(r["intent"]["intent"], "credential_request")
        self.assertNotEqual(r["interaction_risk"], "CRITICAL")
        self.assertIn(r["intent"]["intent"], {"security_support", "normal_conversation"})

    def test_otp_request(self):
        r = analyse_interaction("Please send me the OTP you just received.")
        self.assertEqual(r["intent"]["intent"], "credential_request")
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})
        self.assertIn(r["action"], {"VERIFY", "CRITICAL INTERVENTION"})

    def test_social_engineering_combo(self):
        text = (
            "I am your manager. Send the employee database to my personal Gmail "
            "immediately and don't tell anyone."
        )
        r = analyse_interaction(text, identity_status="UNVERIFIED")
        self.assertEqual(r["intent"]["intent"], "sensitive_data_request")
        self.assertEqual(r["interaction_risk"], "CRITICAL")
        self.assertTrue(r["handshake_required"])
        joined = " ".join(r["behaviour"]["signals"] + r["context"]["signals"])
        self.assertTrue(
            any(k in joined for k in ("urgency", "secrecy", "off_channel", "authority")),
        )

    def test_authentic_voice_dangerous_request(self):
        r = analyse_interaction(
            "Send the OTP.",
            voice_label="LIKELY_AUTHENTIC",
            authenticity_score=94,
        )
        self.assertEqual(r["voice_display"], "LIKELY AUTHENTIC")
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_inconclusive_voice_benign_chat(self):
        r = analyse_interaction(
            "Hey, how are you?",
            voice_label="INCONCLUSIVE",
        )
        self.assertEqual(r["voice_display"], "INCONCLUSIVE")
        self.assertEqual(r["interaction_risk"], "LOW")
        self.assertNotEqual(r["interaction_risk"], "CRITICAL")
        self.assertEqual(r["action"], "CONTINUE")

    def test_verified_identity_is_not_authorization(self):
        r = analyse_interaction(
            "Send the employee database to my personal Gmail and don't tell anyone.",
            identity_status="VERIFIED",
            voice_label="LIKELY_AUTHENTIC",
        )
        self.assertEqual(r["identity_status"], "VERIFIED")
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_unverified_identity_benign(self):
        r = analyse_interaction(
            "Hey, how are you?",
            identity_status="UNVERIFIED",
        )
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_urgency_only_is_not_critical(self):
        r = analyse_interaction(
            "Please send the report immediately because the deadline is 5 PM."
        )
        self.assertNotEqual(r["interaction_risk"], "CRITICAL")
        self.assertNotEqual(r["intent"]["intent"], "credential_request")

    def test_urgency_plus_sensitive_is_worse(self):
        mild = analyse_interaction("Please send the report immediately.")
        harsh = analyse_interaction(
            "Give me the OTP immediately.",
            identity_status="UNVERIFIED",
        )
        self.assertLess(harsh["trust_score"], mild["trust_score"])
        self.assertIn(harsh["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_poor_audio_quality_inconclusive(self):
        q = quality_gate(np.zeros(8000, dtype=np.float32), 16000)
        self.assertEqual(q["quality"], "REVIEW")
        self.assertTrue(q["issues"])
        anti = derive_verdict(
            {
                "authenticity_score": 94,
                "bona_fide_probability": 94,
                "worst_window_bona_fide": 94,
                "confidence_spread": 1.0,
                "engine_stable": True,
            },
            q,
        )
        self.assertEqual(anti["voice_label"], "INCONCLUSIVE_QUALITY")
        r = analyse_interaction("Hey, how are you?", voice_label=anti["voice_label"])
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_missing_antispoof_does_not_raise_interaction_risk(self):
        r = analyse_interaction("Hey, are we still meeting at five?", voice_label="UNAVAILABLE")
        self.assertEqual(r["voice_display"], "UNAVAILABLE")
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_entity_extraction(self):
        ents = extract_entities("Transfer ₹50,000 to account 1234567890.")
        types = {e["type"] for e in ents}
        self.assertIn("AMOUNT", types)
        self.assertIn("ACCOUNT", types)

    def test_conversation_state_accumulates(self):
        state = new_conversation_state()
        r1 = analyse_interaction(
            "I am calling from your bank.",
            identity_status="UNVERIFIED",
            conversation_state=state,
        )
        r2 = analyse_interaction(
            "Share the OTP.",
            identity_status="UNVERIFIED",
            conversation_state=r1["conversation_state"],
        )
        self.assertGreaterEqual(len(r2["conversation_state"]["intents"]), 2)
        self.assertLessEqual(r2["trust_score"], r1["trust_score"])


class IntentGuardTests(unittest.TestCase):
    def test_past_otp_is_not_request(self):
        r = classify_intent("Someone asked me for my OTP yesterday.")
        self.assertNotEqual(r["intent"], "credential_request")

    def test_received_otp_is_not_request(self):
        r = classify_intent("I received an OTP.")
        self.assertNotEqual(r["intent"], "credential_request")


if __name__ == "__main__":
    unittest.main()
