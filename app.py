"""
PsychoMeet — Streamlit Interface
Web UI for uploading audio or transcript and viewing psychological profiles.

Run: streamlit run app.py
"""

import streamlit as st
import json
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Import pipeline functions
from pipeline import (
    transcribe_audio,
    format_transcript_for_analysis,
    load_transcript_file,
    analyze_psychology,
)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="PsychoMeet",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def score_bar(score: int, color: str = "#4F8EF7") -> str:
    """Render a simple HTML progress bar for Big Five scores."""
    pct = max(0, min(100, score))
    return f"""
    <div style="background:#e0e0e0;border-radius:4px;height:10px;width:100%;margin:2px 0 6px 0">
      <div style="background:{color};width:{pct}%;height:10px;border-radius:4px;"></div>
    </div>
    <small style="color:#888">{pct}/100</small>
    """

def emotion_badge(emotion: str) -> str:
    color_map = {
        "calm":         "#4CAF50",
        "anxious":      "#FF9800",
        "enthusiastic": "#2196F3",
        "frustrated":   "#F44336",
        "guarded":      "#9E9E9E",
        "engaged":      "#00BCD4",
        "disengaged":   "#607D8B",
        "stressed":     "#E91E63",
        "confident":    "#3F51B5",
    }
    c = color_map.get(emotion.lower(), "#888")
    return f'<span style="background:{c};color:white;padding:2px 10px;border-radius:12px;font-size:13px">{emotion}</span>'

def flag_badge(text: str, active: bool) -> str:
    if active:
        return f'<span style="background:#FF5252;color:white;padding:2px 8px;border-radius:10px;font-size:12px;margin:2px">⚠ {text}</span>'
    return f'<span style="background:#E0E0E0;color:#888;padding:2px 8px;border-radius:10px;font-size:12px;margin:2px">{text}</span>'

OCEAN_COLORS = {
    "openness":          "#7C4DFF",
    "conscientiousness": "#00BCD4",
    "extraversion":      "#FF9800",
    "agreeableness":     "#4CAF50",
    "neuroticism":       "#F44336",
}

# ─────────────────────────────────────────────
# SIDEBAR — CONFIGURATION
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    assemblyai_key = st.text_input(
        "AssemblyAI API Key",
        value=os.getenv("ASSEMBLYAI_API_KEY", ""),
        type="password",
        help="Get your key at assemblyai.com"
    )
    anthropic_key = st.text_input(
        "Anthropic API Key",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Get your key at console.anthropic.com"
    )

    st.markdown("---")
    context = st.selectbox(
        "Meeting context",
        ["professional meeting", "social gathering", "team brainstorm",
         "client meeting", "performance review", "coaching session"],
        index=0,
    )

    st.markdown("---")
    st.markdown("**Input mode**")
    input_mode = st.radio(
        "",
        ["🎙️ Audio file (via AssemblyAI)", "📄 Text transcript"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("""
    **Stack**
    - AssemblyAI — diarization
    - Claude claude-sonnet-4-6 — profiling
    - Big Five (OCEAN) model

    **Disclaimer**
    *Behavioral profiling only.
    Not a clinical tool.*
    """)

# ─────────────────────────────────────────────
# MAIN — INPUT
# ─────────────────────────────────────────────

st.markdown("# 🧠 PsychoMeet")
st.markdown("*Multi-speaker psychological profiling from conversation audio or transcript*")
st.markdown("---")

transcript_text = None
word_counts = {}

if input_mode == "🎙️ Audio file (via AssemblyAI)":
    uploaded_audio = st.file_uploader(
        "Upload audio recording",
        type=["mp3", "m4a", "wav", "mp4", "ogg"],
        help="10–60 minutes recommended. Minimum 3 speakers for meaningful group dynamics."
    )
    if uploaded_audio:
        st.audio(uploaded_audio)

else:
    st.markdown("**Paste or upload a transcript**")
    st.markdown("Format expected: one line per utterance — `Speaker A: text`")
    transcript_input = st.text_area(
        "Transcript",
        height=280,
        placeholder="Speaker A: Good morning everyone, let's get started.\nSpeaker B: Yes, I wanted to raise a concern about the timeline...\nSpeaker C: I think we have capacity, actually."
    )
    uploaded_txt = st.file_uploader("Or upload .txt file", type=["txt"])
    if uploaded_txt:
        transcript_input = uploaded_txt.read().decode("utf-8")

# ─────────────────────────────────────────────
# MAIN — RUN BUTTON
# ─────────────────────────────────────────────

run_disabled = not assemblyai_key or not anthropic_key
if run_disabled:
    st.warning("Enter both API keys in the sidebar to run analysis.")

if st.button("🔍 Run Analysis", disabled=run_disabled, type="primary", use_container_width=True):

    # Set env vars from UI inputs
    os.environ["ASSEMBLYAI_API_KEY"] = assemblyai_key
    os.environ["ANTHROPIC_API_KEY"] = anthropic_key

    try:
        with st.spinner("Processing..."):

            # --- Audio path ---
            if input_mode == "🎙️ Audio file (via AssemblyAI)":
                if not uploaded_audio:
                    st.error("Please upload an audio file.")
                    st.stop()

                # Save to temp file
                suffix = Path(uploaded_audio.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_audio.read())
                    tmp_path = tmp.name

                st.info("⏳ Transcribing and diarizing audio... (this may take 1–3 min)")
                aai_transcript = transcribe_audio(tmp_path)
                transcript_text, word_counts, _ = format_transcript_for_analysis(aai_transcript)
                os.unlink(tmp_path)

                with st.expander("📄 View formatted transcript"):
                    st.text(transcript_text)

            # --- Transcript path ---
            else:
                raw = transcript_input if transcript_input else ""
                if not raw.strip():
                    st.error("Please provide a transcript.")
                    st.stop()
                transcript_text, word_counts, _ = load_transcript_file.__wrapped__(raw) \
                    if hasattr(load_transcript_file, '__wrapped__') else (raw, {}, {})
                # Simple word count fallback
                if not word_counts:
                    for line in raw.strip().split("\n"):
                        if ":" in line:
                            parts = line.split(":", 1)
                            spk = parts[0].strip()
                            wc = len(parts[1].strip().split())
                            word_counts[spk] = word_counts.get(spk, 0) + wc

            st.info("🧠 Analyzing psychology with Claude...")
            analysis = analyze_psychology(transcript_text, context)

        st.success("✅ Analysis complete")
        st.session_state["analysis"] = analysis
        st.session_state["transcript"] = transcript_text

    except Exception as e:
        st.error(f"Pipeline error: {e}")
        st.stop()

# ─────────────────────────────────────────────
# MAIN — RESULTS
# ─────────────────────────────────────────────

if "analysis" in st.session_state:
    analysis = st.session_state["analysis"]
    meta = analysis.get("session_metadata", {})
    speakers = analysis.get("speakers", [])
    group = analysis.get("group_dynamics", {})

    # ── Session overview
    st.markdown("---")
    st.markdown("## 📊 Session Overview")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Speakers", meta.get("speaker_count", "?"))
    c2.metric("Total words", meta.get("total_word_count", "?"))
    c3.metric("Confidence", meta.get("analysis_confidence", "?"))
    c4.metric("Group tension", f"{meta.get('overall_group_tension','?')}/10")
    c5.metric("Cohesion", f"{meta.get('group_cohesion','?')}/10")

    # ── Group dynamics
    st.markdown("---")
    st.markdown("## 👥 Group Dynamics")
    gd_col1, gd_col2 = st.columns([1, 2])
    with gd_col1:
        st.markdown(f"**Power structure:** {group.get('power_structure','?')}")
        st.markdown(f"**Dominant speaker:** {group.get('dominant_speaker','?')}")
        st.markdown(f"**Most collaborative:** {group.get('most_collaborative','?')}")
        st.markdown(f"**Most at risk:** `{group.get('most_at_risk','?')}`")
        tensions = group.get("key_tension_pairs", [])
        if tensions:
            pairs = ", ".join([" ↔ ".join(p) for p in tensions])
            st.markdown(f"**Tension pairs:** {pairs}")
    with gd_col2:
        st.info(group.get("group_summary", ""))

    # ── Individual profiles
    st.markdown("---")
    st.markdown("## 👤 Individual Profiles")

    tabs = st.tabs([s["speaker_id"] for s in speakers])

    for tab, speaker in zip(tabs, speakers):
        with tab:
            sid = speaker["speaker_id"]
            bf = speaker.get("big_five", {})
            em = speaker.get("emotional_state", {})
            cs = speaker.get("communication_style", {})
            ip = speaker.get("interpersonal_dynamics", {})
            flags = speaker.get("risk_flags", {})

            col_a, col_b = st.columns([1, 1])

            with col_a:
                st.markdown("#### 🧬 Big Five (OCEAN)")
                for trait, color in OCEAN_COLORS.items():
                    trait_data = bf.get(trait, {})
                    score = trait_data.get("score", 0)
                    evidence = trait_data.get("evidence", "")
                    st.markdown(f"**{trait.capitalize()}**")
                    st.markdown(score_bar(score, color), unsafe_allow_html=True)
                    if evidence:
                        st.caption(f'*"{evidence}"*')

            with col_b:
                st.markdown("#### 💬 Emotional State")
                dom_em = em.get("dominant_emotion", "?")
                st.markdown(emotion_badge(dom_em), unsafe_allow_html=True)
                st.markdown("")
                st.markdown(f"**Emotional stability:** {em.get('emotional_stability','?')}/10")
                st.markdown(f"**Positive affect:** {em.get('positive_affect','?')}/10")
                stress_signals = em.get("stress_indicators", [])
                if stress_signals:
                    st.markdown("**Stress indicators:**")
                    for s in stress_signals:
                        st.markdown(f"- {s}")

                st.markdown("#### 🗣️ Communication Style")
                st.markdown(f"**Style:** `{cs.get('style','?')}`")
                st.markdown(f"**Vocabulary:** {cs.get('vocabulary_complexity','?')}")
                st.markdown(f"**Hedging:** {cs.get('use_of_hedging','?')}")
                st.markdown(f"**Self-reference (I/me):** {cs.get('use_of_first_person_singular','?')}")
                patterns = cs.get("notable_patterns", [])
                if patterns:
                    st.markdown("**Notable patterns:**")
                    for p in patterns:
                        st.markdown(f"- {p}")

            st.markdown("#### ⚠️ Risk Flags")
            flag_html = (
                flag_badge("Elevated anxiety", flags.get("elevated_anxiety", False)) +
                flag_badge("Social withdrawal", flags.get("social_withdrawal", False)) +
                flag_badge("Potential conflict", flags.get("potential_conflict", False)) +
                flag_badge("Disengagement", flags.get("disengagement", False))
            )
            st.markdown(flag_html, unsafe_allow_html=True)

            st.markdown("#### 📝 Summary")
            st.info(speaker.get("summary", ""))

    # ── Downloads
    st.markdown("---")
    st.markdown("## 💾 Export")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            "⬇️ Download JSON report",
            data=json.dumps(analysis, indent=2),
            file_name="psychomeet_report.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_dl2:
        if "transcript" in st.session_state:
            st.download_button(
                "⬇️ Download transcript",
                data=st.session_state["transcript"],
                file_name="transcript.txt",
                mime="text/plain",
                use_container_width=True,
            )
