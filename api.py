"""
WeVibe — FastAPI Backend
Exposes the Python pipeline as a REST API for the mobile app.

Run:
    uvicorn api:app --reload --port 8000

Endpoints:
    GET  /health
    POST /analyze/transcript   { transcript, context }
    POST /analyze/audio        multipart/form-data (file + context)
"""

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from pipeline import (
    analyze_psychology,
    load_transcript_file,
    transcribe_audio,
    format_transcript_for_analysis,
)

app = FastAPI(title="WeVibe API", version="1.0.0-mvp")

# CORS — allow all origins for local dev (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────

class TranscriptRequest(BaseModel):
    transcript: str
    context: str = "professional meeting"


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    """Liveness check."""
    return {
        "status": "ok",
        "version": "1.0.0-mvp",
        "assemblyai_configured": bool(os.getenv("ASSEMBLYAI_API_KEY")),
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


@app.post("/analyze/transcript")
async def analyze_transcript(req: TranscriptRequest):
    """
    Analyze a pre-existing text transcript.
    Skips AssemblyAI — goes directly to Claude.
    """
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")

    try:
        # Compute word counts from text
        word_counts = {}
        for line in req.transcript.strip().split("\n"):
            if ":" in line:
                parts = line.split(":", 1)
                speaker = parts[0].strip()
                words = len(parts[1].strip().split())
                word_counts[speaker] = word_counts.get(speaker, 0) + words

        result = analyze_psychology(req.transcript, req.context)
        result["word_counts"] = word_counts
        result["input_mode"] = "transcript"
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze/audio")
async def analyze_audio(
    file: UploadFile = File(...),
    context: str = Form(default="professional meeting"),
    speakers_expected: int = Form(default=None),
):
    """
    Upload an audio file.
    Pipeline: AssemblyAI diarization → Claude psychological analysis.
    speakers_expected: 1-5 (None = auto-detect)
    Accepts: .m4a, .mp3, .wav, .mp4
    """
    allowed_extensions = {".m4a", ".mp3", ".wav", ".mp4", ".aac", ".ogg"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Use {allowed_extensions}",
        )

    tmp_path = None
    try:
        # Save upload to temp file
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Transcribe + diarize via AssemblyAI (with speaker hint if provided)
        aai_transcript = transcribe_audio(tmp_path, speakers_expected=speakers_expected)
        transcript_text, word_counts, speaker_map = format_transcript_for_analysis(aai_transcript)

        # Psychological analysis via Claude
        result = analyze_psychology(transcript_text, context)
        result["word_counts"] = word_counts
        result["formatted_transcript"] = transcript_text
        result["input_mode"] = "audio"
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {str(e)}")

    finally:
        if tmp_path and Path(tmp_path).exists():
            os.unlink(tmp_path)
