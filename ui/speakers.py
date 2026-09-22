"""Trusted Speaker Gallery — enrollment and profile management UI."""

from __future__ import annotations

from html import escape

import streamlit as st

from models.speaker_registry import (
    MAX_SAMPLES,
    MIN_SAMPLES,
    SAMPLE_FORMATS,
    create_profile,
    delete_profile,
    enroll_profile,
    get_profile,
    list_profiles,
    re_enroll_profile,
    validate_sample,
)
from ui.components import page_header, render
from ui.console import render_topbar


# ---------------------------------------------------------------------------
# Small HTML helpers (keep consistent with the rest of the UI)
# ---------------------------------------------------------------------------

def _badge(text: str, kind: str = "") -> str:
    """Inline status badge.  kind: 'ok' | 'warn' | 'crit' | ''."""
    colors = {
        "ok":   ("color:#3FA36A;border-color:#3FA36A", "✓"),
        "warn": ("color:#C49A3C;border-color:#C49A3C", "⚠"),
        "crit": ("color:#C45C5C;border-color:#C45C5C", "✕"),
        "":     ("color:#9AA6B5;border-color:#253041",  "·"),
    }
    style, icon = colors.get(kind, colors[""])
    return (
        f'<span style="font-size:12px;border:1px solid;border-radius:3px;'
        f'padding:1px 7px;{style}">{icon} {escape(text)}</span>'
    )


def _profile_card_html(p: dict) -> str:
    enrolled = p.get("enrolled", False)
    badge = _badge("ENROLLED", "ok") if enrolled else _badge("NOT ENROLLED", "warn")
    name = escape(p.get("name") or "—")
    role = escape(p.get("role") or "—")
    count = int(p.get("sample_count", 0))
    return f"""
    <div class="tv-card" style="margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="font-size:16px;font-weight:600">{name}</div>
          <div class="tv-dim" style="margin-top:2px">{role}</div>
        </div>
        <div>{badge}</div>
      </div>
      <div class="tv-row" style="margin-top:10px">
        <span>Voice samples</span><span>{count}</span>
      </div>
    </div>
    """


def _sample_status_html(index: int, result: dict) -> str:
    ok = result.get("ok", False)
    dur = result.get("duration")
    fname = result.get("filename", f"sample {index}")
    dur_s = f"{dur:.1f} s" if dur is not None else "—"
    if ok:
        q = (result.get("quality") or {}).get("quality", "")
        badge = _badge(f"OK · {dur_s} · {q}", "ok")
    else:
        badge = _badge("FAILED", "crit")
    return f"""
    <div class="tv-row">
      <span>Sample {index} — {escape(fname)}</span>
      <span>{badge}</span>
    </div>
    """


# ---------------------------------------------------------------------------
# Gallery (list view)
# ---------------------------------------------------------------------------

def _render_gallery():
    profiles = list_profiles()
    if not profiles:
        render(st, """
        <div class="tv-card">
          <div class="tv-card-title">No registered speakers</div>
          <div class="tv-muted">
            Create a profile to enroll a trusted speaker.
            Enrolled voice profiles will appear here.
          </div>
        </div>
        """)
        return

    for p in profiles:
        render(st, _profile_card_html(p))
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("Open", key=f"open_{p['id']}", use_container_width=True):
                st.session_state.speakers_view = "detail"
                st.session_state.speakers_selected_id = p["id"]
                st.rerun()
        with col2:
            if st.button("Delete", key=f"del_{p['id']}", use_container_width=True):
                st.session_state.speakers_confirm_delete = p["id"]
                st.rerun()

    # Confirm-delete modal (inline)
    cid = st.session_state.get("speakers_confirm_delete")
    if cid:
        full = get_profile(cid)
        name = (full or {}).get("name", "this profile")
        st.warning(f"Delete speaker profile **{name}**? This cannot be undone.")
        yes, no = st.columns(2)
        with yes:
            if st.button("Confirm delete", key="del_confirm", use_container_width=True):
                delete_profile(cid)
                st.session_state.speakers_confirm_delete = None
                st.success("Profile deleted.")
                st.rerun()
        with no:
            if st.button("Cancel", key="del_cancel", use_container_width=True):
                st.session_state.speakers_confirm_delete = None
                st.rerun()


# ---------------------------------------------------------------------------
# Create-profile form
# ---------------------------------------------------------------------------

def _render_create_form():
    render(st, '<div class="tv-card-title">New speaker profile</div>')
    with st.form("create_speaker_form", clear_on_submit=True):
        name = st.text_input("Full name *", placeholder="e.g. Priya Sharma")
        role = st.text_input("Role / department", placeholder="e.g. Branch Manager")
        submitted = st.form_submit_button("Create profile", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("Name is required.")
        else:
            try:
                profile = create_profile(name, role)
                st.session_state.speakers_view = "detail"
                st.session_state.speakers_selected_id = profile["id"]
                st.success(f"Profile created for **{profile['name']}**. Now upload voice samples below.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


# ---------------------------------------------------------------------------
# Detail / enrollment view
# ---------------------------------------------------------------------------

def _render_detail(profile_id: str):
    profile = get_profile(profile_id)
    if not profile:
        st.error("Profile not found.")
        if st.button("Back to gallery"):
            st.session_state.speakers_view = "gallery"
            st.rerun()
        return

    name = profile.get("name", "—")
    role = profile.get("role", "—")
    enrolled = profile.get("enrolled", False)

    # Header
    render(st, f"""
    <div class="tv-card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="font-size:20px;font-weight:600">{escape(name)}</div>
          <div class="tv-dim">{escape(role)}</div>
        </div>
        <div>{_badge("ENROLLED", "ok") if enrolled else _badge("NOT ENROLLED", "warn")}</div>
      </div>
    </div>
    """)

    if enrolled:
        _render_enrolled_info(profile)
    else:
        _render_enrollment_form(profile_id, profile)

    st.markdown("---")
    left, right = st.columns(2)
    with left:
        if st.button("← Back to gallery", use_container_width=True, key="back_gallery"):
            st.session_state.speakers_view = "gallery"
            st.session_state.speakers_selected_id = None
            st.rerun()
    with right:
        if enrolled:
            if st.button("Re-enroll (clear voice data)", use_container_width=True, key="reenroll_btn"):
                re_enroll_profile(profile_id)
                st.info("Enrollment cleared. Upload new samples to re-enroll.")
                st.rerun()


def _render_enrolled_info(profile: dict):
    samples = profile.get("samples") or []
    render(st, '<div class="tv-card-title">Enrollment information</div>')
    import time as _time
    enrolled_at = profile.get("enrolled_at")
    enrolled_str = (
        _time.strftime("%Y-%m-%d %H:%M", _time.localtime(enrolled_at))
        if enrolled_at else "—"
    )
    render(st, f"""
    <div class="tv-card">
      <div class="tv-row"><span>Enrolled at</span><span>{escape(enrolled_str)}</span></div>
      <div class="tv-row"><span>Voice samples used</span><span>{len(samples)}</span></div>
      <div class="tv-row"><span>Embedding</span><span>Mean AASIST CM logit vector</span></div>
    </div>
    """)

    if samples:
        render(st, '<div class="tv-section" style="margin-top:12px">Sample details</div>')
        rows = ""
        for s in samples:
            dur = s.get("duration")
            dur_s = f"{dur:.1f} s" if dur is not None else "—"
            quality = s.get("quality", "—")
            issues = "; ".join(s.get("issues") or []) or "None"
            rows += (
                f"<tr><td>{escape(str(s.get('index', '')))}</td>"
                f"<td>{escape(str(s.get('filename', '—')))}</td>"
                f"<td class='num'>{escape(dur_s)}</td>"
                f"<td>{escape(quality)}</td>"
                f"<td class='tv-dim'>{escape(issues)}</td></tr>"
            )
        render(st, f"""
        <div class="tv-card">
          <table class="tv-table">
            <tr><th>#</th><th>File</th><th class="num">Duration</th><th>Quality</th><th>Notes</th></tr>
            {rows}
          </table>
        </div>
        """)
    st.caption(
        "Voice data is processed locally. Embeddings are derived from AASIST "
        "window-level countermeasure logits and are not a guarantee of identity."
    )


def _render_enrollment_form(profile_id: str, profile: dict):
    render(st, '<div class="tv-card-title">Voice enrollment</div>')
    render(st, f"""
    <div class="tv-card" style="margin-bottom:12px">
      <div class="tv-muted">
        Upload <strong>{MIN_SAMPLES}–{MAX_SAMPLES} voice samples</strong> from this speaker.
        Each sample must be at least 1.5 seconds of clear speech.
      </div>
      <div class="tv-dim" style="margin-top:6px">
        Accepted formats: WAV · MP3 · M4A · FLAC · OGG · AAC.
        Longer files are trimmed to the first {120} s.
      </div>
    </div>
    """)

    uploaded_files = st.file_uploader(
        f"Upload {MIN_SAMPLES}–{MAX_SAMPLES} voice samples",
        type=SAMPLE_FORMATS,
        accept_multiple_files=True,
        key=f"enroll_upload_{profile_id}",
        help=f"Select {MIN_SAMPLES} to {MAX_SAMPLES} audio files. All common formats are supported.",
    )

    if not uploaded_files:
        st.caption("No files selected yet. Upload samples to proceed.")
        return

    count = len(uploaded_files)
    if count > MAX_SAMPLES:
        st.warning(f"You uploaded {count} files. Only the first {MAX_SAMPLES} will be used.")
        uploaded_files = uploaded_files[:MAX_SAMPLES]
        count = MAX_SAMPLES

    if count < MIN_SAMPLES:
        st.warning(
            f"You uploaded {count} file(s). "
            f"Please upload at least {MIN_SAMPLES} samples for reliable enrollment."
        )

    # Validate all samples and show per-sample status
    render(st, '<div class="tv-section">Sample validation</div>')
    validation_results: list[dict] = []
    all_ok = True
    for i, f in enumerate(uploaded_files):
        raw = f.getvalue()
        result = validate_sample(raw, f.name)
        result["filename"] = f.name
        validation_results.append(result)
        render(st, _sample_status_html(i + 1, result))
        if result.get("warnings"):
            for w in result["warnings"]:
                st.caption(f"⚠ Sample {i+1}: {w}")
        if not result.get("ok"):
            for err in result.get("errors", []):
                st.error(f"Sample {i+1} ({f.name}): {err}")
            all_ok = False

    valid_count = sum(1 for r in validation_results if r.get("ok"))
    st.caption(f"{valid_count} of {count} sample(s) passed validation.")

    # Enroll button
    if valid_count < MIN_SAMPLES:
        st.error(
            f"Enrollment requires at least {MIN_SAMPLES} valid samples. "
            f"Only {valid_count} passed. Please fix the errors above."
        )
        return

    if st.button(
        f"Enroll speaker ({valid_count} sample{'s' if valid_count != 1 else ''})",
        use_container_width=True,
        key=f"enroll_btn_{profile_id}",
        type="primary",
    ):
        with st.spinner("Generating speaker embedding… this may take a moment."):
            try:
                enroll_profile(
                    profile_id,
                    validation_results,
                    model_key=st.session_state.get("model_choice", "aasist"),
                    allow_download=True,
                )
                st.success(
                    f"Speaker **{profile.get('name', 'Unknown')}** enrolled successfully "
                    f"with {valid_count} voice sample(s)."
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Enrollment failed: {exc}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def render_speakers():
    """Main render function called from app.py."""
    render_topbar("Trusted Speakers")

    # Initialise session state keys
    if "speakers_view" not in st.session_state:
        st.session_state.speakers_view = "gallery"
    if "speakers_selected_id" not in st.session_state:
        st.session_state.speakers_selected_id = None
    if "speakers_confirm_delete" not in st.session_state:
        st.session_state.speakers_confirm_delete = None

    view = st.session_state.get("speakers_view", "gallery")

    # Tab-like nav strip
    col_gallery, col_create = st.columns([3, 1])
    with col_gallery:
        if st.button(
            "Registered Speakers",
            key="spk_nav_gallery",
            use_container_width=True,
            type="primary" if view == "gallery" else "secondary",
        ):
            st.session_state.speakers_view = "gallery"
            st.session_state.speakers_selected_id = None
            st.rerun()
    with col_create:
        if st.button(
            "+ New Profile",
            key="spk_nav_create",
            use_container_width=True,
            type="primary" if view == "create" else "secondary",
        ):
            st.session_state.speakers_view = "create"
            st.session_state.speakers_selected_id = None
            st.rerun()

    st.markdown("---")

    if view == "gallery":
        _render_gallery()
    elif view == "create":
        _render_create_form()
    elif view == "detail" and st.session_state.speakers_selected_id:
        _render_detail(st.session_state.speakers_selected_id)
    else:
        st.session_state.speakers_view = "gallery"
        st.rerun()
