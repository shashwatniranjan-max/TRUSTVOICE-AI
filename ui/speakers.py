"""Registered speaker gallery for TRUSTVOICE prototype."""

import streamlit as st

from models.speaker import dependency_status, enroll_speaker, list_speakers, match_audio_bytes
from utils.audio import DECODE_FORMAT_HELP


def render_speakers():
    st.title("Registered Speaker Gallery")
    st.caption(
        "Enroll known speakers from consented samples, then compare incoming audio against their speaker embeddings. "
        "Similarity is identity evidence, not proof of identity."
    )

    status = dependency_status()
    if not status["ok"]:
        st.warning(status["error"])
        st.info("The rest of TRUSTVOICE continues to work; install the speaker encoder dependency to enable this page.")
        return

    tab_enroll, tab_match, tab_registry = st.tabs(["Enroll Speaker", "Match Voice", "Registry"])

    with tab_enroll:
        st.subheader("Create a speaker profile")
        name = st.text_input("Name", placeholder="Shashwat")
        role = st.text_input("Role / context", placeholder="Finance Manager")
        files = st.file_uploader(
            "Upload 3–5 consented voice samples",
            type=["wav", "mp3", "mpeg", "mpga", "m4a", "aac", "ogg", "opus", "oga", "flac", "webm"],
            accept_multiple_files=True,
            key="speaker_enroll_files",
            help="Use different short speech samples from the same speaker. Do not enroll people without consent.",
        )
        if files:
            st.caption(f"{len(files)} sample(s) selected. Recommended: 3–5.")
            for f in files:
                st.audio(f)
        if st.button("Register voice profile", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Enter a speaker name.")
            elif len(files or []) < 3:
                st.error("Please provide at least 3 samples.")
            else:
                try:
                    with st.spinner("Generating speaker embeddings..."):
                        record = enroll_speaker(
                            name,
                            role,
                            [(f.getvalue(), f.name) for f in files[:5]],
                        )
                    st.success(
                        f"Registered {record['name']} with {record['sample_count']} samples. "
                        "Raw samples are not required for matching after enrollment."
                    )
                except Exception as exc:
                    st.error(f"Enrollment failed: {type(exc).__name__}: {exc}")

    with tab_match:
        st.subheader("Match incoming audio")
        incoming = st.file_uploader(
            "Upload a voice sample",
            type=["wav", "mp3", "mpeg", "mpga", "m4a", "aac", "ogg", "opus", "oga", "flac", "webm"],
            key="speaker_match_file",
        )
        if incoming:
            st.audio(incoming)
        if st.button("Find closest registered speaker", use_container_width=True):
            if incoming is None:
                st.warning("Upload an audio sample first.")
            elif not list_speakers():
                st.warning("No speakers are registered yet.")
            else:
                try:
                    with st.spinner("Extracting speaker embedding and searching profiles..."):
                        matches = match_audio_bytes(incoming.getvalue(), incoming.name, top_k=3)
                    if not matches:
                        st.info("No usable speaker profiles were found.")
                    else:
                        st.markdown("### Speaker matches")
                        for idx, item in enumerate(matches, start=1):
                            st.metric(
                                f"#{idx} {item['name']}",
                                f"{item['similarity']:.1f}% similarity",
                                help="Cosine similarity between the incoming embedding and the best enrolled sample. This is not a calibrated identity probability.",
                            )
                            if item.get("role"):
                                st.caption(f"Role: {item['role']} · enrolled samples: {item['sample_count']}")
                except Exception as exc:
                    st.error(f"Matching failed: {type(exc).__name__}: {exc}")

    with tab_registry:
        st.subheader("Registered profiles")
        records = list_speakers()
        if not records:
            st.info("No speaker profiles enrolled yet.")
        else:
            for record in records:
                with st.container(border=True):
                    left, right = st.columns([2, 1])
                    with left:
                        st.markdown(f"**{record['name']}**")
                        if record.get("role"):
                            st.caption(record["role"])
                    with right:
                        st.caption(f"{record['sample_count']} samples · v{record['version']}")

    st.divider()
    st.caption(
        "Privacy note: voice embeddings are sensitive identity-related data. For the SIH prototype, keep the registry local, use consented samples, and provide deletion/retention controls before any production deployment."
    )
