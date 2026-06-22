# PsychoMeet MVP
**Multi-speaker psychological profiling from conversation audio or transcript**

---

## What it does

1. Takes an audio recording OR a text transcript of a meeting / conversation
2. Identifies each speaker (diarization via AssemblyAI)
3. Analyzes each speaker's psychology via Claude (Big Five, emotional state, communication style, risk flags)
4. Produces an individual profile per speaker + group dynamics report

---

## Setup — 3 steps

### Step 1 — Get your API keys

| Service | Where | Cost |
|---|---|---|
| AssemblyAI | https://www.assemblyai.com → Dashboard → API Keys | ~$0.65/hour audio |
| Anthropic | https://console.anthropic.com → API Keys | ~$0.003/1k tokens |

### Step 2 — Install

```bash
# Clone / download this folder, then:
cd psycho_mvp

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate       # Mac/Linux
# venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and paste your keys
```

### Step 3 — Run

**Option A — Web interface (recommended)**
```bash
streamlit run app.py
```
Opens at http://localhost:8501
Enter API keys in the sidebar, upload audio or paste transcript, click Run.

**Option B — Command line**
```bash
# From audio file
python pipeline.py --audio recording.m4a --context "quarterly review"

# From existing transcript
python pipeline.py --transcript sample_transcript.txt --context "team meeting"

# Custom output file
python pipeline.py --transcript sample_transcript.txt --output my_report.json
```

---

## Test without audio

A sample transcript is included (`sample_transcript.txt`) — a fictional 3-person
quarterly review meeting. Use it to validate the analysis pipeline without
needing an audio file or AssemblyAI credits.

```bash
python pipeline.py --transcript sample_transcript.txt
```

---

## Output structure

The pipeline produces a `report.json` file with this structure:

```
{
  session_metadata: {
    speaker_count, total_word_count, overall_group_tension, group_cohesion, ...
  },
  speakers: [
    {
      speaker_id: "Speaker A",
      big_five: { openness, conscientiousness, extraversion, agreeableness, neuroticism },
      emotional_state: { dominant_emotion, emotional_stability, stress_indicators, ... },
      communication_style: { style, interruptions_tendency, vocabulary_complexity, ... },
      interpersonal_dynamics: { dominant_in_group, conflict_tendency, ... },
      risk_flags: { elevated_anxiety, social_withdrawal, potential_conflict, disengagement },
      summary: "..."
    }
  ],
  group_dynamics: {
    power_structure, dominant_speaker, key_tension_pairs, group_summary, ...
  }
}
```

---

## File structure

```
psycho_mvp/
├── app.py                  ← Streamlit web interface
├── pipeline.py             ← Core pipeline (CLI + functions)
├── prompt_system.py        ← Psychological analysis prompt (the AI brain)
├── requirements.txt        ← Python dependencies
├── .env.example            ← API key template
├── sample_transcript.txt   ← Test transcript (no audio needed)
└── README.md
```

---

## Cost estimate (per session)

| Session length | AssemblyAI | Claude API | Total |
|---|---|---|---|
| 15 min / 3 speakers | ~$0.16 | ~$0.04 | **~$0.20** |
| 30 min / 5 speakers | ~$0.33 | ~$0.07 | **~$0.40** |
| 60 min / 8 speakers | ~$0.65 | ~$0.12 | **~$0.77** |

---

## Legal / ethical notice

- Always obtain **explicit consent** from all participants before recording
- Do not use for clinical diagnosis
- This is behavioral and linguistic profiling, not psychiatry
- Compliant use requires GDPR / APPI (Japan) consent mechanisms in production

---

## Next steps (Phase 2)

- iOS native app (Swift + AVFoundation for real-time recording)
- On-device Whisper for transcription (privacy-first)
- Hume AI integration for acoustic emotional analysis
- Dashboard with session history and longitudinal tracking
- Export to PDF for coaches / HR professionals
