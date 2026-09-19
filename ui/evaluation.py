"""Model evaluation lab. Metrics appear only for labelled user samples."""

from datetime import datetime

import streamlit as st

from models.antispoof import MODEL_REGISTRY
from ui.components import render
from ui.console import render_topbar
from utils.evaluation import evaluate_labeled_voice_set


def render_evaluation():
    render_topbar()
    render(st, '<div class="tv-section">Evaluation lab</div>')
    st.caption(
        "Filename prefixes REAL_ / SPOOF_ (also BONAFIDE_ / FAKE_) label samples. "
        "No metrics are shown until labelled files are actually evaluated. "
        "These figures describe only the files you uploaded, not a published accuracy claim."
    )
    eval_files = st.file_uploader(
        "Labelled evaluation set",
        type=["wav", "mp3", "m4a", "ogg", "flac", "mp4", "webm", "mov", "mkv", "avi"],
        accept_multiple_files=True,
        key="evaluation_dataset",
    )
    if st.button("Run labelled evaluation", use_container_width=True):
        if not eval_files:
            st.warning("Upload labelled REAL_ and SPOOF_ files first.")
        else:
            with st.spinner("Evaluating labelled audio…"):
                try:
                    st.session_state.accuracy_eval = evaluate_labeled_voice_set(
                        eval_files,
                        threshold=float(st.session_state.bona_threshold),
                        model_key=st.session_state.model_choice,
                    )
                except Exception as exc:
                    st.session_state.accuracy_eval = {"error": f"{type(exc).__name__}: {exc}"}

    ev = st.session_state.get("accuracy_eval")
    if not ev:
        st.info("No evaluation has been run in this session.")
        return
    if ev.get("error"):
        st.error(ev["error"])
        return
    if not ev.get("n"):
        st.warning("No valid labelled samples found. Use REAL_… and SPOOF_… filenames.")
        return

    m1, m2, m3, m4 = st.columns(4, gap="small")
    for col, label, key in (
        (m1, "Accuracy", "accuracy"),
        (m2, "Precision", "precision"),
        (m3, "Recall", "recall"),
        (m4, "F1", "f1"),
    ):
        with col:
            render(st, f"""
            <div class="tv-panel">
              <div class="tv-kicker">{label}</div>
              <div class="tv-value small">{ev[key]*100:.1f}%</div>
            </div>
            """)

    e1, e2, e3 = st.columns(3, gap="small")
    with e1:
        far = ev.get("far")
        render(st, f"""
        <div class="tv-panel">
          <div class="tv-kicker">FAR</div>
          <div class="tv-label">{'n/a' if far is None else f'{far*100:.1f}%'}</div>
          <div class="tv-muted">Spoof accepted as authentic</div>
        </div>
        """)
    with e2:
        frr = ev.get("frr")
        render(st, f"""
        <div class="tv-panel">
          <div class="tv-kicker">FRR</div>
          <div class="tv-label">{'n/a' if frr is None else f'{frr*100:.1f}%'}</div>
          <div class="tv-muted">Authentic rejected as spoof</div>
        </div>
        """)
    with e3:
        eer = ev.get("eer")
        render(st, f"""
        <div class="tv-panel">
          <div class="tv-kicker">EER</div>
          <div class="tv-label">{'n/a' if eer is None else f'{eer*100:.2f}%'}</div>
          <div class="tv-muted">Threshold-independent operating point on this set</div>
        </div>
        """)

    cm = ev.get("confusion") or {}
    render(st, f"""
    <div class="tv-panel" style="margin-top:12px">
      <div class="tv-kicker">Confusion matrix (rows = truth)</div>
      <div class="tv-row"><span></span><span>Pred authentic</span><span>Pred spoof</span></div>
      <div class="tv-row"><span>Truth authentic</span><span>{cm.get('tn', 0)}</span><span>{cm.get('fp', 0)}</span></div>
      <div class="tv-row"><span>Truth spoof</span><span>{cm.get('fn', 0)}</span><span>{cm.get('tp', 0)}</span></div>
      <div class="tv-muted" style="margin-top:8px">
        Samples: {ev['n']} valid ({ev.get('n_real', 0)} real, {ev.get('n_spoof', 0)} spoof) ·
        False positives: {ev.get('fp', 0)} · False negatives: {ev.get('fn', 0)}
      </div>
    </div>
    """)

    if ev.get("false_positives"):
        st.write("False positives (authentic → spoof):", ev["false_positives"])
    if ev.get("false_negatives"):
        st.write("False negatives (spoof → authentic):", ev["false_negatives"])

    n_real, n_spoof = ev.get("n_real", 0), ev.get("n_spoof", 0)
    st.write(
        f"Current threshold: {st.session_state.bona_threshold:.3f} · "
        f"decision band ±{st.session_state.decision_band:.3f} · "
        f"source: {st.session_state.threshold_source}"
    )
    st.write(f"Labelled real samples in this run: {n_real}. Spoof samples: {n_spoof}.")

    if ev.get("eer") is not None and ev.get("suggested_threshold") is not None:
        st.info(
            f"EER on this set: {ev['eer']*100:.2f}%. "
            f"Suggested operating threshold from these files: {ev['suggested_threshold']:.3f}."
        )
        if st.button("Adopt threshold from this labelled set", use_container_width=True):
            st.session_state.bona_threshold = float(ev["suggested_threshold"])
            st.session_state.threshold_source = (
                f"calibrated on {ev['n']} labelled samples, "
                f"{datetime.now().strftime('%d %b %Y %H:%M')}"
            )
            st.success("Threshold updated for this session. Re-run live analysis to refresh verdicts.")
            st.rerun()
    elif n_real < 1 or n_spoof < 1:
        st.warning("Threshold not calibrated — using prototype default. EER needs both REAL_ and SPOOF_ files.")
    else:
        st.warning("Threshold not calibrated — using prototype default.")

    if ev["n"] < 30:
        st.warning(
            f"Only {ev['n']} labelled samples. Figures this small have wide error bars and "
            "must not be quoted as product accuracy."
        )

    st.dataframe(ev["rows"], use_container_width=True, hide_index=True)
    st.caption(
        f"Active model: {MODEL_REGISTRY[st.session_state.model_choice]['label']}. "
        "Measured on this labelled set only."
    )
