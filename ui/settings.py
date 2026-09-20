"""Countermeasure and threshold controls."""

import streamlit as st

from models.antispoof import MODEL_DIR, MODEL_REGISTRY
from models.asr import asr_model_name
from ui.components import render
from ui.console import render_topbar


def render_settings():
    render_topbar("Settings")
    render(st, '<div class="tv-card-title">Analysis</div>')
    st.caption(
        "The default 0.50 threshold is a prototype starting point, not a calibrated probability. "
        "Use the evaluation lab when you have labelled REAL_ and SPOOF_ files."
    )

    keys = list(MODEL_REGISTRY.keys())
    chosen = st.selectbox(
        "Active anti-spoof model",
        keys,
        index=keys.index(st.session_state.model_choice),
        format_func=lambda k: f"{MODEL_REGISTRY[k]['label']} · {MODEL_REGISTRY[k]['approx_size']}",
    )
    if chosen != st.session_state.model_choice:
        st.session_state.model_choice = chosen
        st.session_state.last_analysis = None
        st.warning(
            f"Switched to {MODEL_REGISTRY[chosen]['label']}. Previous audio results were cleared "
            "because scores from different checkpoints are not comparable."
        )

    t1, t2 = st.columns(2)
    with t1:
        new_threshold = st.slider(
            "Authenticity threshold", 0.05, 0.95,
            float(st.session_state.bona_threshold), 0.01,
        )
    with t2:
        new_band = st.slider(
            "Uncertainty band", 0.0, 0.40,
            float(st.session_state.decision_band), 0.01,
        )
    if new_threshold != st.session_state.bona_threshold:
        st.session_state.bona_threshold = float(new_threshold)
        st.session_state.threshold_source = "manual override"
    if new_band != st.session_state.decision_band:
        st.session_state.decision_band = float(new_band)

    src = st.session_state.threshold_source
    if src.startswith("default"):
        st.info("Threshold not calibrated — using prototype default.")

    render(st, '<div class="tv-card-title" style="margin-top:16px">Audio / ASR</div>')
    render(st, f"""
    <div class="tv-card">
      <table class="tv-table">
        <tr><td>Model</td><td>{MODEL_REGISTRY[st.session_state.model_choice]['label']}</td></tr>
        <tr><td>Threshold</td><td class="num">{st.session_state.bona_threshold:.3f}</td></tr>
        <tr><td>Decision band</td><td class="num">±{st.session_state.decision_band:.3f}</td></tr>
        <tr><td>Threshold source</td><td>{src}</td></tr>
        <tr><td>ASR model</td><td>{asr_model_name()} (TRUSTVOICE_ASR_MODEL)</td></tr>
        <tr><td>Model directory</td><td>{MODEL_DIR}</td></tr>
        <tr><td>Execution</td><td>CPU · 1 thread · sequential</td></tr>
      </table>
    </div>
    """)
    st.caption(MODEL_REGISTRY[st.session_state.model_choice]["note"])
    render(st, '<div class="tv-card-title" style="margin-top:16px">Prototype information</div>')
    st.caption(
        "Prototype processing is local to the application environment. Voice/audio data should "
        "be treated as sensitive and retained only as long as necessary. Set TRUSTVOICE_MODEL_PATH "
        "to run fully offline. Set TRUSTVOICE_ASR_MODEL (default tiny) for local Whisper ASR. "
        "This prototype does not intercept ordinary cellular calls and does "
        "not enroll a production speaker gallery."
    )
