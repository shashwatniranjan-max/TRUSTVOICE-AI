"""Model Evaluation & Benchmarking Engine for TRUSTVOICE AI.

Implements rigorous biometric countermeasure metrics, EER calculation,
LFCC-GMM baseline, dataset manifest validation, reproducible logging,
and scenario-based risk pipeline evaluation.
"""

from __future__ import annotations

import csv
import io
import os
import platform
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.fftpack
from sklearn.metrics import roc_auc_score
from sklearn.mixture import GaussianMixture

from models.antispoof import analyze_audio_bytes, sigmoid
from risk.config import DEFAULT_BONA_THRESHOLD
from risk.pipeline import analyse_interaction

# ── Published Literature Reference Benchmarks (ASVspoof 2019 LA) ───────────
# Source: Published papers on the ASVspoof 2019 Logical Access (LA) Evaluation set.
PUBLISHED_BENCHMARKS = [
    {
        "model": "AASIST",
        "authors": "Jee-weon Jung et al. (2022)",
        "venue": "IEEE ICASSP 2022",
        "architecture": "Spectro-Temporal Graph Attention Network",
        "dataset": "ASVspoof 2019 LA Eval (71,237 samples)",
        "eer_percent": 0.83,
        "min_tdcf": 0.0275,
        "parameters": "~297K",
        "input_features": "Raw waveform (16 kHz, ~4s)",
        "citation": "AASIST: Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks, ICASSP 2022. arXiv:2110.01200",
        "doi_url": "https://doi.org/10.1109/ICASSP43922.2022.9747766",
    },
    {
        "model": "AASIST-L",
        "authors": "Jee-weon Jung et al. (2022)",
        "venue": "IEEE ICASSP 2022",
        "architecture": "Lightweight Graph Attention Network",
        "dataset": "ASVspoof 2019 LA Eval (71,237 samples)",
        "eer_percent": 0.99,
        "min_tdcf": 0.0347,
        "parameters": "~85K",
        "input_features": "Raw waveform (16 kHz, ~4s)",
        "citation": "AASIST: Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks, ICASSP 2022. arXiv:2110.01200",
        "doi_url": "https://arxiv.org/abs/2110.01200",
    },
    {
        "model": "RawNet2",
        "authors": "Hemlata Tak et al. (2021)",
        "venue": "Interspeech 2021",
        "architecture": "Dilated Residual CNN + GRU Backbone",
        "dataset": "ASVspoof 2019 LA Eval (71,237 samples)",
        "eer_percent": 5.41,
        "min_tdcf": 0.2230,
        "parameters": "~17.8M",
        "input_features": "Raw waveform (16 kHz, ~4s)",
        "citation": "End-to-End spectro-temporal graph attention networks for speaker verification and spoofing countermeasures, 2021.",
        "doi_url": "https://doi.org/10.21437/Interspeech.2021-1250",
    },
    {
        "model": "LFCC-GMM (Baseline)",
        "authors": "Md Sahidullah et al. (2019)",
        "venue": "ASVspoof 2019 Baseline",
        "architecture": "60-dim LFCC + 512-component GMM",
        "dataset": "ASVspoof 2019 LA Eval (71,237 samples)",
        "eer_percent": 8.09,
        "min_tdcf": 0.2116,
        "parameters": "Statistical GMM",
        "input_features": "Linear Frequency Cepstral Coefficients + Δ + ΔΔ",
        "citation": "Introduction to the third ASVspoof challenge: Automatic speaker verification spoofing and countermeasures, 2019.",
        "doi_url": "https://doi.org/10.21437/Interspeech.2019-2580",
    },
    {
        "model": "CQCC-GMM (Baseline)",
        "authors": "Massimiliano Todisco et al. (2019)",
        "venue": "ASVspoof 2019 Baseline",
        "architecture": "Constant Q Cepstral Coefficients + 512-component GMM",
        "dataset": "ASVspoof 2019 LA Eval (71,237 samples)",
        "eer_percent": 9.57,
        "min_tdcf": 0.2366,
        "parameters": "Statistical GMM",
        "input_features": "Constant Q Transform Cepstral Coefficients",
        "citation": "ASVspoof 2019: Automatic Speaker Verification Spoofing and Countermeasures Challenge database, 2019.",
        "doi_url": "https://doi.org/10.1016/j.csl.2016.03.003",
    },
]


def get_hardware_info() -> Dict[str, Any]:
    """Capture current machine hardware for benchmark execution reporting."""
    return {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "processor": platform.processor() or "Unknown CPU",
        "python_version": platform.python_version(),
        "execution_provider": "CPUExecutionProvider (ONNX Sequential)",
        "timestamp": datetime.now().isoformat(),
    }


# ── Metric Calculations & EER ───────────────────────────────────────────────

def compute_eer_interpolated(
    scores: np.ndarray | list, labels: np.ndarray | list
) -> Tuple[Optional[float], Optional[float]]:
    """
    Compute the Equal Error Rate (EER) and operating threshold using linear interpolation.

    Convention:
      - labels: 1 = bona_fide, 0 = spoof
      - scores: continuous countermeasure score (higher = more likely bona_fide)
      - FAR(θ): fraction of spoofs accepted as bona_fide (score >= θ)
      - FRR(θ): fraction of bona_fide rejected as spoof (score < θ)
    """
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int32)
    n_bona = np.sum(labels == 1)
    n_spoof = np.sum(labels == 0)

    if n_bona == 0 or n_spoof == 0 or len(scores) == 0:
        return None, None

    thresholds = np.unique(scores)
    thresholds = np.sort(thresholds)

    far_list, frr_list = [], []
    for th in thresholds:
        far = np.sum((labels == 0) & (scores >= th)) / n_spoof
        frr = np.sum((labels == 1) & (scores < th)) / n_bona
        far_list.append(far)
        frr_list.append(frr)

    far_arr = np.array(far_list)
    frr_arr = np.array(frr_list)

    # Find crossing index where FAR and FRR curves intersect
    diff = far_arr - frr_arr
    idx = np.where(diff <= 0)[0]

    if len(idx) == 0:
        return float(far_arr[-1]), float(thresholds[-1])
    if idx[0] == 0:
        return float(far_arr[0]), float(thresholds[0])

    i = idx[0]
    # Linear interpolation between points (i-1) and i
    x0, x1 = thresholds[i - 1], thresholds[i]
    far0, far1 = far_arr[i - 1], far_arr[i]
    frr0, frr1 = frr_arr[i - 1], frr_arr[i]

    denom = (far1 - far0) - (frr1 - frr0)
    if abs(denom) < 1e-12:
        eer = (far0 + frr0) / 2.0
        th_eer = (x0 + x1) / 2.0
    else:
        t = (frr0 - far0) / denom
        t = float(np.clip(t, 0.0, 1.0))
        eer = far0 + t * (far1 - far0)
        th_eer = x0 + t * (x1 - x0)

    return float(eer), float(th_eer)


def calculate_classification_metrics(
    y_true: list[int] | np.ndarray,
    y_pred: list[int] | np.ndarray,
    scores: Optional[list[float] | np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Calculate full biometric countermeasure metrics.

    Conventions explicitly documented:
      Positive class (1) = SPOOF (Threat detection convention)
      Negative class (0) = BONA_FIDE (Authentic speech)
      TP: Spoof correctly predicted as Spoof
      TN: Bona fide correctly predicted as Bona Fide
      FP: Bona fide incorrectly flagged as Spoof (False Rejection of genuine user)
      FN: Spoof incorrectly accepted as Bona Fide (False Acceptance of attacker)
    """
    y_true = np.asarray(y_true, dtype=np.int32)
    y_pred = np.asarray(y_pred, dtype=np.int32)
    total = len(y_true)

    if total == 0:
        return {
            "total_samples": 0, "n_bona_fide": 0, "n_spoof": 0,
            "tp": 0, "tn": 0, "fp": 0, "fn": 0,
            "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1_score": 0.0,
            "specificity": 0.0, "far": None, "frr": None,
            "eer": None, "eer_threshold": None, "roc_auc": None,
            "positive_class": "1 = SPOOF",
        }

    n_spoof = int(np.sum(y_true == 1))
    n_bona = int(np.sum(y_true == 0))

    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    accuracy = (tp + tn) / total
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    # FAR: False Acceptance Rate = Spoof accepted as authentic = fn / n_spoof
    far = (fn / n_spoof) if n_spoof > 0 else None
    # FRR: False Rejection Rate = Bona fide rejected as spoof = fp / n_bona
    frr = (fp / n_bona) if n_bona > 0 else None

    # EER and ROC-AUC from continuous scores
    eer, eer_threshold = None, None
    roc_auc = None

    if scores is not None and len(scores) == total and n_bona > 0 and n_spoof > 0:
        scores_arr = np.asarray(scores, dtype=np.float64)
        # Convert to bona_fide=1, spoof=0 for standard EER countermeasure formula
        labels_bona = 1 - y_true
        eer, eer_threshold = compute_eer_interpolated(scores_arr, labels_bona)

        # ROC-AUC: Probability of spoof (1) having higher spoof-score than bona-fide (0)
        # If score is cm_score (higher = bona), spoof score is -cm_score
        try:
            spoof_scores = -scores_arr
            roc_auc = float(roc_auc_score(y_true, spoof_scores))
        except Exception:
            roc_auc = None

    return {
        "total_samples": total,
        "n_bona_fide": n_bona,
        "n_spoof": n_spoof,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": round(float(accuracy), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "specificity": round(float(specificity), 4),
        "f1_score": round(float(f1), 4),
        "far": round(float(far), 4) if far is not None else None,
        "frr": round(float(frr), 4) if frr is not None else None,
        "eer": round(float(eer), 4) if eer is not None else None,
        "eer_threshold": round(float(eer_threshold), 4) if eer_threshold is not None else None,
        "roc_auc": round(float(roc_auc), 4) if roc_auc is not None else None,
        "positive_class": "1 = SPOOF (Threat), 0 = BONA_FIDE (Authentic)",
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


# ── LFCC Feature Extraction & GMM Baseline ──────────────────────────────────

def compute_lfcc(
    audio: np.ndarray,
    sr: int = 16000,
    n_filters: int = 20,
    n_ceps: int = 20,
    frame_len: int = 400,
    hop_len: int = 160,
) -> np.ndarray:
    """
    Extract Linear Frequency Cepstral Coefficients (LFCC) with delta coefficients.
    Standard baseline feature representation for ASVspoof countermeasure models.
    """
    audio = np.asarray(audio, dtype=np.float32).flatten()
    if len(audio) < frame_len:
        audio = np.pad(audio, (0, frame_len - len(audio)))

    num_frames = 1 + (len(audio) - frame_len) // hop_len
    indices = (
        np.tile(np.arange(frame_len), (num_frames, 1))
        + np.tile(np.arange(0, num_frames * hop_len, hop_len), (frame_len, 1)).T
    )
    frames = audio[indices] * np.hamming(frame_len)

    # FFT magnitude spectrum
    n_fft = 512
    mag = np.abs(np.fft.rfft(frames, n=n_fft))  # shape: (num_frames, 257)

    # Linear triangular filterbank (0 to sr/2)
    freqs = np.linspace(0, sr / 2, n_fft // 2 + 1)
    filter_freqs = np.linspace(0, sr / 2, n_filters + 2)
    fb = np.zeros((n_filters, len(freqs)))
    for m in range(1, n_filters + 1):
        left, center, right = filter_freqs[m - 1], filter_freqs[m], filter_freqs[m + 1]
        for k, f in enumerate(freqs):
            if left <= f <= center and center > left:
                fb[m - 1, k] = (f - left) / (center - left)
            elif center <= f <= right and right > center:
                fb[m - 1, k] = (right - f) / (right - center)

    energies = np.dot(mag, fb.T)
    energies = np.maximum(energies, 1e-12)
    log_e = np.log(energies)

    # Discrete Cosine Transform (DCT-II)
    lfcc = scipy.fftpack.dct(log_e, type=2, axis=1, norm="ortho")[:, :n_ceps]

    # Delta (first derivative)
    deltas = np.zeros_like(lfcc)
    if len(lfcc) > 2:
        deltas[1:-1] = (lfcc[2:] - lfcc[:-2]) / 2.0

    return np.hstack([lfcc, deltas])  # (num_frames, 40)


class LfccGmmBaseline:
    """
    Lightweight LFCC-GMM anti-spoofing baseline.
    Estimates log-likelihood ratio: log P(X | bona_fide) - log P(X | spoof).
    """

    def __init__(self, n_components: int = 4):
        self.n_components = n_components
        self.gmm_bona = None
        self.gmm_spoof = None
        self.is_trained = False
        self.train_samples_count = 0

    def fit(self, bona_audios: list[np.ndarray], spoof_audios: list[np.ndarray], sr: int = 16000) -> None:
        """Fit dual Gaussian mixture models on training partitions."""
        bona_feats = []
        for a in bona_audios:
            f = compute_lfcc(a, sr=sr)
            bona_feats.append(f)

        spoof_feats = []
        for a in spoof_audios:
            f = compute_lfcc(a, sr=sr)
            spoof_feats.append(f)

        if not bona_feats or not spoof_feats:
            raise ValueError("Training split requires both bona_fide and spoof audio samples.")

        X_bona = np.vstack(bona_feats)
        X_spoof = np.vstack(spoof_feats)

        os.environ["OMP_NUM_THREADS"] = "1"
        self.gmm_bona = GaussianMixture(
            n_components=min(self.n_components, max(1, len(X_bona) // 10)),
            covariance_type="diag",
            max_iter=30,
            random_state=42,
        )
        self.gmm_bona.fit(X_bona)

        self.gmm_spoof = GaussianMixture(
            n_components=min(self.n_components, max(1, len(X_spoof) // 10)),
            covariance_type="diag",
            max_iter=30,
            random_state=42,
        )
        self.gmm_spoof.fit(X_spoof)

        self.is_trained = True
        self.train_samples_count = len(bona_audios) + len(spoof_audios)

    def score(self, audio: np.ndarray, sr: int = 16000) -> float:
        """Compute log-likelihood ratio countermeasure score."""
        if not self.is_trained:
            raise RuntimeError("LFCC-GMM baseline has not been trained yet.")
        feats = compute_lfcc(audio, sr=sr)
        log_prob_bona = np.mean(self.gmm_bona.score_samples(feats))
        log_prob_spoof = np.mean(self.gmm_spoof.score_samples(feats))
        return float(log_prob_bona - log_prob_spoof)


# ── Manifest Loader & Validator ─────────────────────────────────────────────

def parse_and_validate_manifest(
    manifest_text_or_bytes: str | bytes,
    available_filenames: Optional[set[str]] = None,
) -> Dict[str, Any]:
    """
    Parse a CSV/TSV manifest mapping audio files to ground-truth labels.
    Conforms to ASVspoof / standard countermeasure benchmark protocols.
    """
    if isinstance(manifest_text_or_bytes, bytes):
        text = manifest_text_or_bytes.decode("utf-8", errors="replace")
    else:
        text = str(manifest_text_or_bytes)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {"valid": False, "error": "Manifest is empty.", "records": []}

    # Detect separator (comma, tab, or whitespace)
    sample = lines[0]
    if "\t" in sample:
        delimiter = "\t"
    elif "," in sample:
        delimiter = ","
    else:
        delimiter = None  # whitespace split

    reader = csv.reader(io.StringIO(text), delimiter=delimiter) if delimiter else [l.split() for l in lines]
    rows = list(reader)

    if not rows:
        return {"valid": False, "error": "No valid data rows found in manifest.", "records": []}

    header = [str(c).strip().lower() for c in rows[0]]
    has_header = any(h in {"filename", "file", "audio", "label", "target"} for h in header)

    data_rows = rows[1:] if has_header else rows
    fn_idx, label_idx, attack_idx, split_idx = 0, 1, -1, -1

    if has_header:
        for idx, col in enumerate(header):
            if col in {"filename", "file", "audio", "path", "audio_path"}:
                fn_idx = idx
            elif col in {"label", "ground_truth", "class", "target"}:
                label_idx = idx
            elif col in {"attack_type", "attack", "system_id", "tag"}:
                attack_idx = idx
            elif col in {"split", "partition", "subset"}:
                split_idx = idx

    VALID_LABELS = {"bonafide", "bona_fide", "real", "genuine", "authentic", "1", "spoof", "fake", "synthetic", "cloned", "deepfake", "0"}
    records = []
    skipped = []
    for r in data_rows:
        if not r or len(r) < 2:
            continue

        # Handle headerless space-separated protocols (e.g. ASVspoof standard)
        curr_fn_idx = fn_idx
        curr_lbl_idx = label_idx
        curr_atk_idx = attack_idx

        if not has_header:
            if r[-1].strip().lower() in VALID_LABELS:
                curr_lbl_idx = len(r) - 1
                # Find audio file column
                ext_match = [idx for idx, val in enumerate(r) if val.strip().lower().endswith((".flac", ".wav", ".mp3", ".ogg", ".m4a"))]
                if ext_match:
                    curr_fn_idx = ext_match[0]
                elif len(r) == 5:
                    curr_fn_idx = 1  # Standard ASVspoof: SPEAKER_ID AUDIO_ID - ATTACK KEY
                    curr_atk_idx = 3
                else:
                    curr_fn_idx = 0

        if len(r) <= max(curr_fn_idx, curr_lbl_idx) or curr_fn_idx < 0:
            continue

        fname = os.path.basename(r[curr_fn_idx].strip())
        raw_label = r[curr_lbl_idx].strip().lower()

        # Label normalization
        if raw_label in {"bonafide", "bona_fide", "real", "genuine", "authentic", "1"}:
            label = "bona_fide"
        elif raw_label in {"spoof", "fake", "synthetic", "cloned", "deepfake", "0"}:
            label = "spoof"
        else:
            skipped.append((fname, f"Unknown label '{raw_label}'"))
            continue

        attack_type = r[curr_atk_idx].strip() if (curr_atk_idx != -1 and len(r) > curr_atk_idx) else "unknown"
        split = r[split_idx].strip().lower() if (split_idx != -1 and len(r) > split_idx) else "eval"

        file_exists = (available_filenames is None) or (fname in available_filenames)
        records.append({
            "filename": fname,
            "label": label,
            "attack_type": attack_type,
            "split": split,
            "file_available": file_exists,
        })

    n_bona = sum(1 for r in records if r["label"] == "bona_fide")
    n_spoof = sum(1 for r in records if r["label"] == "spoof")
    available_count = sum(1 for r in records if r["file_available"])

    return {
        "valid": len(records) > 0,
        "error": None if records else "No valid labeled records could be parsed.",
        "total_records": len(records),
        "available_files_count": available_count,
        "n_bona_fide": n_bona,
        "n_spoof": n_spoof,
        "splits": sorted(list({r["split"] for r in records})),
        "attack_types": sorted(list({r["attack_type"] for r in records if r["attack_type"] != "unknown"})),
        "records": records,
        "skipped": skipped,
    }


# ── Full Dataset Voice Model Evaluator ──────────────────────────────────────

def evaluate_audio_voice_dataset(
    audio_items: list[tuple[str, bytes]],
    manifest_records: list[dict],
    model_key: str = "aasist",
    threshold: float = DEFAULT_BONA_THRESHOLD,
    band: float = 0.0,
    selected_split: str = "ALL",
) -> Dict[str, Any]:
    """
    Evaluate audio samples against ground-truth labels using real model inference.
    Collects execution timings, continuous scores, and biometric metrics.
    """
    manifest_map = {r["filename"]: r for r in manifest_records}
    name_to_bytes = {name: b for name, b in audio_items}

    # Filter by split if selected
    eval_filenames = []
    for fname, r in manifest_map.items():
        if selected_split != "ALL" and r.get("split", "").upper() != selected_split.upper():
            continue
        if fname in name_to_bytes:
            eval_filenames.append(fname)

    if not eval_filenames:
        return {
            "status": "NO_MATCHING_SAMPLES",
            "error": "No matching audio files found for the selected split and manifest.",
            "metrics": calculate_classification_metrics([], []),
            "predictions": [],
        }

    predictions = []
    y_true, y_pred, cm_scores = [], [], []
    latencies_ms = []

    t_eval_start = time.time()
    for fname in eval_filenames:
        raw_bytes = name_to_bytes[fname]
        rec = manifest_map[fname]
        ground_truth = rec["label"]  # 'bona_fide' or 'spoof'

        t0 = time.time()
        res = analyze_audio_bytes(
            raw_bytes,
            fname,
            model_key=model_key,
            threshold=threshold,
            band=band,
            allow_download=False,
        )
        latency = (time.time() - t0) * 1000.0
        latencies_ms.append(latency)

        anti = res.get("anti_spoof") or {}
        verdict = anti.get("voice_label", "INCONCLUSIVE")
        cm_val = anti.get("cm_score")
        auth_score = anti.get("authenticity_score", 0)

        # Decision rule: score01 >= threshold -> bona_fide, else -> spoof
        # (Handling inconclusive as non-authentic when conservative threshold applied)
        score01 = float(auth_score) / 100.0
        predicted_class = "bona_fide" if score01 >= threshold else "spoof"

        true_num = 1 if ground_truth == "spoof" else 0
        pred_num = 1 if predicted_class == "spoof" else 0

        # Classification result categorization
        if predicted_class == ground_truth:
            result_tag = "CORRECT"
        elif ground_truth == "spoof" and predicted_class == "bona_fide":
            result_tag = "FALSE_ACCEPTANCE"  # FAR event
        else:
            result_tag = "FALSE_REJECTION"   # FRR event

        y_true.append(true_num)
        y_pred.append(pred_num)
        if cm_val is not None:
            cm_scores.append(float(cm_val))
        else:
            cm_scores.append(0.0)

        predictions.append({
            "filename": fname,
            "ground_truth": ground_truth,
            "predicted_class": predicted_class,
            "verdict": verdict,
            "result_tag": result_tag,
            "cm_score": cm_val,
            "authenticity_score": auth_score,
            "bona_fide_prob": anti.get("bona_fide_probability"),
            "attack_type": rec.get("attack_type", "unknown"),
            "split": rec.get("split", "eval"),
            "duration": res.get("duration"),
            "latency_ms": round(latency, 1),
        })

    t_eval_total = time.time() - t_eval_start
    metrics = calculate_classification_metrics(y_true, y_pred, scores=cm_scores)

    # Attack type breakdown
    attack_breakdown = {}
    for p in predictions:
        atk = p["attack_type"]
        if atk not in attack_breakdown:
            attack_breakdown[atk] = {"total": 0, "correct": 0, "missed": 0}
        attack_breakdown[atk]["total"] += 1
        if p["result_tag"] == "CORRECT":
            attack_breakdown[atk]["correct"] += 1
        else:
            attack_breakdown[atk]["missed"] += 1

    for atk, data in attack_breakdown.items():
        data["accuracy"] = round((data["correct"] / data["total"]) * 100, 1) if data["total"] else 0.0

    return {
        "status": "SUCCESS",
        "model_key": model_key,
        "model_name": "AASIST (Bundled ONNX)",
        "selected_split": selected_split,
        "samples_evaluated": len(predictions),
        "threshold_used": threshold,
        "total_eval_time_s": round(t_eval_total, 2),
        "mean_latency_ms": round(float(np.mean(latencies_ms)), 1) if latencies_ms else 0.0,
        "throughput_samples_per_sec": round(len(predictions) / t_eval_total, 2) if t_eval_total > 0 else 0.0,
        "metrics": metrics,
        "attack_breakdown": attack_breakdown,
        "predictions": predictions,
        "false_acceptances": [p for p in predictions if p["result_tag"] == "FALSE_ACCEPTANCE"],
        "false_rejections": [p for p in predictions if p["result_tag"] == "FALSE_REJECTION"],
        "hardware": get_hardware_info(),
    }


# ── Complete Pipeline Scenario Evaluation ───────────────────────────────────

PIPELINE_SCENARIOS = [
    {
        "id": "SCN-01",
        "name": "Tech Support Malware Extortion",
        "text": "Hello, this is Sandhouse from Microsoft. Your computer has virus. You need to send me $30,000 to fix it.",
        "voice_label": "UNAVAILABLE",
        "identity_status": "UNVERIFIED",
        "ground_truth_risk": "CRITICAL",
        "category": "Extortion / Cyber Threat",
        "description": "Caller claims Microsoft authority, announces malware infection, demands $30,000 wire transfer.",
    },
    {
        "id": "SCN-02",
        "name": "Fake Police Arrest Extortion",
        "text": "I am calling from police department. You will be arrested. You must pay $2,000 immediately.",
        "voice_label": "UNAVAILABLE",
        "identity_status": "UNVERIFIED",
        "ground_truth_risk": "CRITICAL",
        "category": "Extortion / Authority Coercion",
        "description": "Impersonates police, threatens immediate arrest, demands urgent wire transfer.",
    },
    {
        "id": "SCN-03",
        "name": "Urgent Bank OTP Extraction",
        "text": "I am calling from your bank security team. Share the OTP right now or your account will be permanently blocked.",
        "voice_label": "UNAVAILABLE",
        "identity_status": "UNVERIFIED",
        "ground_truth_risk": "CRITICAL",
        "category": "Credential Extraction",
        "description": "Caller demands live OTP under threat of permanent account termination.",
    },
    {
        "id": "SCN-04",
        "name": "Verified Biometric Identity · Off-Channel Data Exfiltration",
        "text": "Hey, it's me. Send the complete employee database to my personal Gmail right now. Keep this secret.",
        "voice_label": "LIKELY_AUTHENTIC",
        "identity_status": "VERIFIED",
        "ground_truth_risk": "CRITICAL",
        "category": "Data Exfiltration / Insider Threat",
        "description": "Verified colleague asks for proprietary database over personal email under secrecy.",
    },
    {
        "id": "SCN-05",
        "name": "Synthetic Voice · Benign Interaction Pretext",
        "text": "Hey, are we still meeting for lunch at five o'clock? Let me know if the time works.",
        "voice_label": "LIKELY_SPOOF",
        "identity_status": "UNVERIFIED",
        "ground_truth_risk": "HIGH",
        "category": "Deepfake Voice Exploit",
        "description": "Synthetic voice countermeasure detection paired with non-sensitive meeting talk.",
    },
    {
        "id": "SCN-06",
        "name": "Speaker Biometric Mismatch · Financial Request",
        "text": "Please transfer fifty thousand rupees to account 1234567890 immediately.",
        "voice_label": "LIKELY_AUTHENTIC",
        "identity_status": "MISMATCH",
        "ground_truth_risk": "CRITICAL",
        "category": "Speaker Biometric Impersonation",
        "description": "Enrolled profile voiceprint fails biometric match while demanding funds transfer.",
    },
    {
        "id": "SCN-07",
        "name": "Security Awareness Advice (Benign False Positive Test)",
        "text": "Remember, legitimate bank agents will never ask for your OTP or password. Never share it with anyone.",
        "voice_label": "LIKELY_AUTHENTIC",
        "identity_status": "UNVERIFIED",
        "ground_truth_risk": "LOW",
        "category": "Benign Discussion (Advice)",
        "description": "Conversation explains OTP security and advises against sharing secrets.",
    },
    {
        "id": "SCN-08",
        "name": "Past Phishing Report (Benign False Positive Test)",
        "text": "Someone called me yesterday and asked for my OTP, but I hung up immediately.",
        "voice_label": "LIKELY_AUTHENTIC",
        "identity_status": "UNVERIFIED",
        "ground_truth_risk": "LOW",
        "category": "Benign Discussion (Past Report)",
        "description": "Reporting a past phishing event, not a live credential extraction request.",
    },
    {
        "id": "SCN-09",
        "name": "Standard Workplace Report Request",
        "text": "Can you send me yesterday's meeting notes and the project presentation when you have time?",
        "voice_label": "LIKELY_AUTHENTIC",
        "identity_status": "UNVERIFIED",
        "ground_truth_risk": "LOW",
        "category": "Benign Workplace",
        "description": "Everyday office request without pressure, urgency, or sensitive data solicitation.",
    },
    {
        "id": "SCN-10",
        "name": "Casual Scheduling Call",
        "text": "Hey, how are you doing today? Let's catch up after the standup meeting.",
        "voice_label": "LIKELY_AUTHENTIC",
        "identity_status": "UNVERIFIED",
        "ground_truth_risk": "LOW",
        "category": "Benign Casual",
        "description": "Standard friendly conversation with zero sensitive entities or indicators.",
    },
]


def run_pipeline_scenario_benchmark() -> Dict[str, Any]:
    """
    Run the complete TRUSTVOICE multi-dimensional risk pipeline across
    the standardized scenario test suite. Measures risk classification accuracy,
    threat sensitivity, and false-alarm rates.
    """
    results = []
    y_true_binary, y_pred_binary = [], []  # 1 = THREAT (HIGH/CRITICAL), 0 = BENIGN (LOW/ELEVATED)
    risk_levels = ["LOW", "ELEVATED", "HIGH", "CRITICAL"]
    matrix = {true_lvl: {pred_lvl: 0 for pred_lvl in risk_levels} for true_lvl in risk_levels}

    correct_exact = 0
    t0 = time.time()

    for scn in PIPELINE_SCENARIOS:
        res = analyse_interaction(
            transcript=scn["text"],
            voice_label=scn["voice_label"],
            identity_status=scn["identity_status"],
            source="BENCHMARK",
        )

        pred_risk = res["interaction_risk"]
        true_risk = scn["ground_truth_risk"]
        is_exact = pred_risk == true_risk

        if is_exact:
            correct_exact += 1

        if true_risk in matrix and pred_risk in matrix[true_risk]:
            matrix[true_risk][pred_risk] += 1

        # Binary threat detection: THREAT = CRITICAL or HIGH, BENIGN = LOW or ELEVATED
        is_threat_true = true_risk in {"HIGH", "CRITICAL"}
        is_threat_pred = pred_risk in {"HIGH", "CRITICAL"}
        y_true_binary.append(1 if is_threat_true else 0)
        y_pred_binary.append(1 if is_threat_pred else 0)

        results.append({
            "id": scn["id"],
            "name": scn["name"],
            "category": scn["category"],
            "ground_truth_risk": true_risk,
            "predicted_risk": pred_risk,
            "trust_score": res["trust_score"],
            "intent": res["intent"]["intent"],
            "action": res["action"],
            "safety_gates_fired": res["gates"],
            "passing": is_exact,
        })

    total_time = time.time() - t0
    total = len(PIPELINE_SCENARIOS)

    # Calculate threat detection metrics (Sensitivity / Precision on High/Critical attacks)
    tp_threat = sum(1 for t, p in zip(y_true_binary, y_pred_binary) if t == 1 and p == 1)
    tn_threat = sum(1 for t, p in zip(y_true_binary, y_pred_binary) if t == 0 and p == 0)
    fp_threat = sum(1 for t, p in zip(y_true_binary, y_pred_binary) if t == 0 and p == 1)
    fn_threat = sum(1 for t, p in zip(y_true_binary, y_pred_binary) if t == 1 and p == 0)

    threat_recall = tp_threat / (tp_threat + fn_threat) if (tp_threat + fn_threat) else 0.0
    threat_precision = tp_threat / (tp_threat + fp_threat) if (tp_threat + fp_threat) else 0.0
    false_alarm_rate = fp_threat / (fp_threat + tn_threat) if (fp_threat + tn_threat) else 0.0
    miss_rate = fn_threat / (fn_threat + tp_threat) if (fn_threat + tp_threat) else 0.0

    return {
        "total_scenarios": total,
        "exact_accuracy_percent": round((correct_exact / total) * 100, 1),
        "threat_sensitivity_percent": round(threat_recall * 100, 1),
        "threat_precision_percent": round(threat_precision * 100, 1),
        "false_alarm_rate_percent": round(false_alarm_rate * 100, 1),
        "miss_rate_percent": round(miss_rate * 100, 1),
        "execution_time_ms": round(total_time * 1000, 1),
        "confusion_matrix": matrix,
        "scenario_results": results,
        "evaluation_timestamp": datetime.now().isoformat(),
    }
