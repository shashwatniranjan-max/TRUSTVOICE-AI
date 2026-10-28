"""Unit and integration tests for Model Evaluation & Benchmarking module."""

import numpy as np
import pytest

from utils.benchmarking import (
    PIPELINE_SCENARIOS,
    PUBLISHED_BENCHMARKS,
    LfccGmmBaseline,
    calculate_classification_metrics,
    compute_eer_interpolated,
    compute_lfcc,
    parse_and_validate_manifest,
    run_pipeline_scenario_benchmark,
)


class TestMetricCalculations:
    def test_calculate_classification_metrics_perfect(self):
        # 5 bona_fide (0), 5 spoof (1) - all correctly predicted
        y_true = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
        y_pred = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
        # cm_scores: higher = more bona_fide
        scores = [2.5, 2.0, 1.8, 1.5, 1.2, -1.0, -1.5, -2.0, -2.2, -2.5]

        m = calculate_classification_metrics(y_true, y_pred, scores=scores)
        assert m["total_samples"] == 10
        assert m["accuracy"] == 1.0
        assert m["precision"] == 1.0
        assert m["recall"] == 1.0
        assert m["f1_score"] == 1.0
        assert m["far"] == 0.0  # Zero spoofs accepted as real
        assert m["frr"] == 0.0  # Zero reals rejected as spoof
        assert m["roc_auc"] == 1.0
        assert m["confusion_matrix"] == {"tn": 5, "fp": 0, "fn": 0, "tp": 5}

    def test_calculate_classification_metrics_with_known_errors(self):
        # 4 bona_fide (0), 4 spoof (1)
        # 1 False Positive (bona predicted as spoof) -> FRR = 1/4 = 0.25
        # 1 False Negative (spoof predicted as bona) -> FAR = 1/4 = 0.25
        y_true = [0, 0, 0, 0, 1, 1, 1, 1]
        y_pred = [0, 0, 0, 1, 0, 1, 1, 1]

        m = calculate_classification_metrics(y_true, y_pred)
        assert m["total_samples"] == 8
        assert m["n_bona_fide"] == 4
        assert m["n_spoof"] == 4
        assert m["tp"] == 3
        assert m["tn"] == 3
        assert m["fp"] == 1
        assert m["fn"] == 1
        assert m["accuracy"] == 6 / 8
        assert m["precision"] == 3 / 4
        assert m["recall"] == 3 / 4
        assert m["far"] == 0.25  # fn / n_spoof
        assert m["frr"] == 0.25  # fp / n_bona

    def test_empty_or_single_class_metrics(self):
        # Empty input
        m_empty = calculate_classification_metrics([], [])
        assert m_empty["total_samples"] == 0
        assert m_empty["accuracy"] == 0.0
        assert m_empty["far"] is None

        # Only one class present (no spoofs)
        m_single = calculate_classification_metrics([0, 0], [0, 0])
        assert m_single["total_samples"] == 2
        assert m_single["n_spoof"] == 0
        assert m_single["far"] is None  # Cannot divide by zero spoofs
        assert m_single["frr"] == 0.0

    def test_compute_eer_interpolated(self):
        # Generate known scores with clear crossing
        # Bona fide scores centered at +2.0, Spoof scores centered at -2.0
        np.random.seed(42)
        bona = np.random.normal(loc=2.0, scale=0.8, size=200)
        spoof = np.random.normal(loc=-2.0, scale=0.8, size=200)
        scores = np.concatenate([bona, spoof])
        labels = np.concatenate([np.ones(200), np.zeros(200)])

        eer, th = compute_eer_interpolated(scores, labels)
        assert eer is not None
        assert 0.0 <= eer <= 0.05  # Should have very low EER (~0-2%)
        assert -1.0 <= th <= 1.0   # Crossing threshold should be near zero


class TestManifestParsing:
    def test_parse_valid_csv_manifest(self):
        csv_text = """filename,label,attack_type,split
audio_01.wav,bona_fide,none,eval
audio_02.wav,spoof,A01,eval
audio_03.wav,real,none,train
audio_04.wav,synthetic,TTS,dev
"""
        res = parse_and_validate_manifest(csv_text)
        assert res["valid"] is True
        assert res["total_records"] == 4
        assert res["n_bona_fide"] == 2
        assert res["n_spoof"] == 2
        assert "eval" in res["splits"]
        assert "A01" in res["attack_types"]
        assert "TTS" in res["attack_types"]

    def test_parse_asvspoof_protocol_whitespace(self):
        # Standard ASVspoof space-delimited format
        raw = """LA_0001.flac - - - bonafide
LA_0002.flac - - A02 spoof
LA_0003.flac - - A03 spoof
"""
        res = parse_and_validate_manifest(raw)
        assert res["valid"] is True
        assert res["total_records"] == 3
        assert res["n_bona_fide"] == 1
        assert res["n_spoof"] == 2

    def test_parse_empty_manifest(self):
        res = parse_and_validate_manifest("")
        assert res["valid"] is False
        assert "empty" in res["error"].lower()


class TestLfccFeatureAndGmmBaseline:
    def test_compute_lfcc_dimensions(self):
        sr = 16000
        sig = np.random.randn(sr * 2).astype(np.float32)  # 2 seconds
        lfcc = compute_lfcc(sig, sr=sr, n_filters=20, n_ceps=20)
        assert lfcc.ndim == 2
        assert lfcc.shape[1] == 40  # 20 static + 20 delta
        assert np.all(np.isfinite(lfcc))

    def test_lfcc_gmm_baseline_training_and_scoring(self):
        sr = 16000
        # 3 synthetic bona-fide samples, 3 spoof samples
        bona_audios = [np.random.normal(0, 0.2, sr * 2).astype(np.float32) for _ in range(3)]
        spoof_audios = [np.random.normal(0, 0.5, sr * 2).astype(np.float32) for _ in range(3)]

        model = LfccGmmBaseline(n_components=2)
        assert model.is_trained is False

        model.fit(bona_audios, spoof_audios, sr=sr)
        assert model.is_trained is True

        test_sig = np.random.normal(0, 0.2, sr * 2).astype(np.float32)
        score = model.score(test_sig, sr=sr)
        assert isinstance(score, float)
        assert np.isfinite(score)


class TestPipelineScenarioBenchmark:
    def test_pipeline_scenario_benchmark_runs_and_passes(self):
        res = run_pipeline_scenario_benchmark()
        assert res["total_scenarios"] == 10
        assert res["exact_accuracy_percent"] >= 80.0
        assert res["threat_sensitivity_percent"] >= 80.0
        assert res["threat_precision_percent"] >= 80.0
        assert res["false_alarm_rate_percent"] == 0.0
        assert len(res["scenario_results"]) == 10
        assert "LOW" in res["confusion_matrix"]
        assert "CRITICAL" in res["confusion_matrix"]

    def test_published_benchmarks_catalogued(self):
        assert len(PUBLISHED_BENCHMARKS) >= 5
        models = [p["model"] for p in PUBLISHED_BENCHMARKS]
        assert "AASIST" in models
        assert "RawNet2" in models
        assert "LFCC-GMM (Baseline)" in models
        aasist_pub = next(p for p in PUBLISHED_BENCHMARKS if p["model"] == "AASIST")
        assert aasist_pub["eer_percent"] == 0.83
        assert "ASVspoof 2019" in aasist_pub["dataset"]
