"""Countermeasure and threshold controls."""

import streamlit as st

from models.antispoof import MODEL_DIR, MODEL_REGISTRY
from ui.components import render
from ui.console import render_topbar


def render_settings():
    render_topbar()
    render(st, '<div class="tv-section">Settings</div>')
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

    render(st, f"""
    <div class="tv-panel">
      <div class="tv-row"><span>Model</span><span>{MODEL_REGISTRY[st.session_state.model_choice]['label']}</span></div>
      <div class="tv-row"><span>Threshold</span><span>{st.session_state.bona_threshold:.3f}</span></div>
      <div class="tv-row"><span>Decision band</span><span>±{st.session_state.decision_band:.3f}</span></div>
      <div class="tv-row"><span>Threshold source</span><span>{src}</span></div>
      <div class="tv-row"><span>Model directory</span><span>{MODEL_DIR}</span></div>
      <div class="tv-row"><span>Execution</span><span>CPU · 1 thread · sequential</span></div>
    </div>
    """)
    st.caption(MODEL_REGISTRY[st.session_state.model_choice]["note"])
    st.caption(
        "Prototype processing is local to the application environment. Voice/audio data should "
        "be treated as sensitive and retained only as long as necessary. Set TRUSTVOICE_MODEL_PATH "
        "to run fully offline. This prototype does not intercept ordinary cellular calls and does "
        "not enroll a production speaker gallery."
    )
