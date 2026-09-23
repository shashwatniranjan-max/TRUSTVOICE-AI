"""Settings — system status and prototype analysis preferences."""

from __future__ import annotations

from html import escape

import streamlit as st

from models.antispoof import MODEL_REGISTRY
from models.asr import asr_dependency_status, asr_model_name
from risk.config import DEFAULT_BONA_THRESHOLD, DEFAULT_DECISION_BAND
from ui.theme import COLORS


def render(html: str):
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def render_settings():
    render("""
    <div class="tv-page">
      <div>
        <h1>SETTINGS</h1>
        <p>System status and prototype analysis preferences.</p>
      </div>
    </div>
    """)

    dep = asr_dependency_status()
    asr_ready = dep.get("ok", False)
    asr_status_badge = '<span class="tv-badge tv-badge-ok">● Ready</span>' if asr_ready else \
                       '<span class="tv-badge tv-badge-warn">● Unavailable</span>'

    col_services, col_policy = st.columns([1, 1], gap="medium")

    with col_services:
        render(f"""
        <div class="tv-card">
          <div class="tv-card-title">Analysis services</div>
          <div class="tv-evidence-row">
            <div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Audio preprocessing</div>
              <div style="font-size:12px;color:var(--tv-dim)">Managed by the existing analysis pipeline</div>
            </div>
            <span class="tv-badge tv-badge-ok">● Ready</span>
          </div>
          <div class="tv-evidence-row">
            <div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Voice authenticity</div>
              <div style="font-size:12px;color:var(--tv-dim)">Managed by the existing analysis pipeline</div>
            </div>
            <span class="tv-badge tv-badge-ok">● Ready</span>
          </div>
          <div class="tv-evidence-row">
            <div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Speech-to-text</div>
              <div style="font-size:12px;color:var(--tv-dim)">Managed by the existing analysis pipeline</div>
            </div>
            {asr_status_badge}
          </div>
          <div class="tv-evidence-row" style="border-bottom:0">
            <div>
              <div style="font-size:13.5px;font-weight:600;color:var(--tv-text)">Risk fusion</div>
              <div style="font-size:12px;color:var(--tv-dim)">Managed by the existing analysis pipeline</div>
            </div>
            <span class="tv-badge tv-badge-warn">● Prototype</span>
          </div>
        </div>
        """)

        if not asr_ready:
            st.info(dep.get("error") or "ASR unavailable — faster-whisper may not be installed.")

        # Model selection
        render("""<div class="tv-card" style="margin-top:0">
          <div class="tv-card-title">Anti-spoofing model</div>
        </div>""")
        model_key = st.selectbox(
            "Model",
            list(MODEL_REGISTRY.keys()),
            index=list(MODEL_REGISTRY.keys()).index(st.session_state.model_choice)
            if st.session_state.model_choice in MODEL_REGISTRY else 0,
            format_func=lambda k: MODEL_REGISTRY[k]["label"],
            key="settings_model",
            label_visibility="collapsed",
        )
        if model_key != st.session_state.model_choice:
            st.session_state.model_choice = model_key
            st.success("Model updated.")

        # ASR model info
        render(f"""
        <div class="tv-card" style="margin-top:0">
          <div class="tv-card-title">Speech recognition</div>
          <div class="tv-evidence-row">
            <span class="tv-evidence-label">ASR model</span>
            <span style="font-size:13px;font-weight:500;color:var(--tv-text)">{escape(asr_model_name())}</span>
          </div>
          <div class="tv-evidence-row" style="border-bottom:0">
            <span class="tv-evidence-label">Status</span>
            {'<span class="tv-badge tv-badge-ok">● Available</span>' if asr_ready else '<span class="tv-badge tv-badge-warn">● Unavailable</span>'}
          </div>
        </div>
        """)

    with col_policy:
        render("""<div class="tv-card">
          <div class="tv-card-title">Decision policy</div>
        </div>""")

        # Threshold
        threshold_display = st.selectbox(
            "Verification threshold",
            ["Use backend policy", "Manual"],
            key="settings_thresh_mode",
        )

        current_thresh = float(st.session_state.bona_threshold)
        if threshold_display == "Manual":
            new_thresh = st.slider(
                "Threshold value",
                min_value=0.0,
                max_value=1.0,
                value=current_thresh,
                step=0.005,
                format="%.3f",
                key="settings_thresh_val",
            )
            if new_thresh != current_thresh:
                st.session_state.bona_threshold = new_thresh
                st.session_state.threshold_source = "manual override"

        render(f"""
        <div class="tv-evidence-row" style="margin-top:6px">
          <span class="tv-evidence-label">Current threshold</span>
          <span style="font-size:13px;font-weight:500;color:var(--tv-text)">{current_thresh:.3f}</span>
        </div>
        <div class="tv-evidence-row">
          <span class="tv-evidence-label">Source</span>
          <span style="font-size:13px;color:var(--tv-text)">{escape(str(st.session_state.threshold_source))}</span>
        </div>
        """)

        # Unavailable evidence handling
        unavail_choice = st.selectbox(
            "Unavailable evidence",
            ["Display as not available", "Treat as inconclusive", "Ignore"],
            key="settings_unavail",
        )

        if st.button("Save preferences", use_container_width=True, type="primary", key="settings_save"):
            st.success("Preferences saved for this session.")

        # Reset thresholds
        render("""<div style="margin-top:14px"></div>""")
        if st.button("Reset to defaults", use_container_width=True, key="settings_reset"):
            st.session_state.bona_threshold = DEFAULT_BONA_THRESHOLD
            st.session_state.decision_band = DEFAULT_DECISION_BAND
            st.session_state.threshold_source = "prototype default"
            st.success("Thresholds reset.")
            st.rerun()

        # Band
        render("""<div class="tv-card" style="margin-top:12px">
          <div class="tv-card-title">Decision band</div>
        </div>""")
        current_band = float(st.session_state.decision_band)
        new_band = st.slider(
            "Decision band (±)",
            0.0, 0.25, current_band, 0.005, format="%.3f",
            key="settings_band",
        )
        if new_band != current_band:
            st.session_state.decision_band = new_band

    # Evaluation lab link
    render("""<div style="margin-top:12px"></div>""")
    render("""<div class="tv-card">
      <div class="tv-card-title">Evaluation lab</div>
      <div class="tv-muted" style="margin-bottom:10px">
        Score labelled audio files against the current model. Upload REAL_… and SPOOF_… prefixed files.
      </div>
    </div>""")
    if st.button("→ Open Evaluation Lab", use_container_width=True, key="settings_eval"):
        st.session_state.ui_nav = "Evaluation Lab"
        st.rerun()

    render("""<div class="tv-footer">TRUSTVOICE AI · SIH prototype · settings affect this session only</div>""")
