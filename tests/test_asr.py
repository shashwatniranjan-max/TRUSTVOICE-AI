"""ASR wiring tests. Whisper weights are mocked — no fabricated inference."""

import unittest
from unittest.mock import patch

import numpy as np

from models.asr import resolve_live_transcript, transcribe_pcm
from risk.pipeline import analyse_interaction


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeInfo:
    language = "en"
    language_probability = 0.92


class FakeModel:
    def transcribe(self, audio, **kwargs):
        return iter([FakeSegment("  Please send me the OTP you just received.  ")]), FakeInfo()


class AsrIntegrationTests(unittest.TestCase):
    def test_text_only_analysis_still_works(self):
        r = analyse_interaction("Hey, are we still meeting at five?")
        self.assertEqual(r["intent"]["intent"], "normal_conversation")
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_asr_transcript_feeds_existing_pipeline(self):
        choice = resolve_live_transcript("", {
            "status": "success",
            "transcript": "Please send me the OTP you just received.",
        })
        self.assertTrue(choice["analyze"])
        self.assertEqual(choice["source"], "ASR")
        r = analyse_interaction(choice["text"])
        self.assertEqual(r["intent"]["intent"], "credential_request")
        self.assertIn(r["interaction_risk"], {"HIGH", "CRITICAL"})

    def test_asr_failure_does_not_crash_or_score_empty_text(self):
        out = transcribe_pcm(None, 16000)
        self.assertEqual(out["status"], "decode_failed")
        choice = resolve_live_transcript("", out)
        self.assertFalse(choice["analyze"])
        self.assertEqual(choice["source"], "NONE")
        self.assertIn("could not be automatically analyzed", choice["warning"])

    def test_empty_or_no_speech_is_not_treated_as_benign(self):
        choice = resolve_live_transcript("", {
            "status": "no_speech",
            "transcript": "",
            "error": "ASR returned no speech.",
        })
        self.assertFalse(choice["analyze"])
        self.assertNotEqual(choice["warning"], None)
        # Must not run analyse_interaction("") as a fake LOW conversation.
        self.assertEqual(choice["text"], "")

    def test_manual_transcript_overrides_asr(self):
        choice = resolve_live_transcript(
            "Hey, are we still meeting at five?",
            {
                "status": "success",
                "transcript": "Give me your OTP immediately.",
            },
        )
        self.assertEqual(choice["source"], "MANUAL")
        self.assertTrue(choice["analyze"])
        r = analyse_interaction(choice["text"])
        self.assertEqual(r["intent"]["intent"], "normal_conversation")
        self.assertEqual(r["interaction_risk"], "LOW")

    def test_security_advice_still_not_a_credential_attack(self):
        choice = resolve_live_transcript("", {
            "status": "success",
            "transcript": "The bank will never ask you for your OTP.",
        })
        r = analyse_interaction(choice["text"])
        self.assertNotEqual(r["intent"]["intent"], "credential_request")

    def test_transcribe_pcm_too_long_skips_model(self):
        y = np.zeros(1600, dtype=np.float32)
        out = transcribe_pcm(y, 16000, duration=9999)
        self.assertEqual(out["status"], "too_long")
        self.assertFalse(out["transcript"])

    def test_transcribe_pcm_model_error_is_structured(self):
        y = np.zeros(16000, dtype=np.float32)
        with patch("models.asr.get_whisper_model", side_effect=RuntimeError("oom")):
            out = transcribe_pcm(y, 16000, duration=1.0)
        self.assertEqual(out["status"], "error")
        self.assertIn("oom", out["error"] or "")

    def test_transcribe_pcm_mocked_success_does_not_invent_weights(self):
        y = np.zeros(16000, dtype=np.float32)
        with patch("models.asr.get_whisper_model", return_value=FakeModel()):
            out = transcribe_pcm(y, 16000, duration=1.0)
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["transcript"], "Please send me the OTP you just received.")
        self.assertEqual(out["language"], "en")
        choice = resolve_live_transcript("", out)
        r = analyse_interaction(choice["text"])
        self.assertEqual(r["intent"]["intent"], "credential_request")


if __name__ == "__main__":
    unittest.main()
