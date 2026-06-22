"""
PsychoMeet — Core Pipeline
Audio file → AssemblyAI diarization → Claude psychological analysis → JSON report

Usage:
    python pipeline.py --audio path/to/recording.m4a --context "team meeting"
    python pipeline.py --transcript path/to/transcript.txt --context "social gathering"

Requirements:
    pip install assemblyai anthropic rich typer python-dotenv
"""

import os
import json
import time
import typer
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

import assemblyai as aai
import anthropic

from prompt_system import SYSTEM_PROMPT, build_user_prompt

load_dotenv()
console = Console()
app = typer.Typer()

# ─────────────────────────────────────────────
# 1. ASSEMBLYAI — Transcription + Diarization
# ─────────────────────────────────────────────

def transcribe_audio(audio_path: str) -> dict:
    """
    Send audio file to AssemblyAI.
    Returns structured transcript with speaker labels.
    """
    aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not aai.settings.api_key:
        raise ValueError("ASSEMBLYAI_API_KEY not set in .env")

    config = aai.TranscriptionConfig(
        speaker_labels=True,          # Enable diarization
        speakers_expected=None,       # Auto-detect speaker count
        language_code="en",           # English
        punctuate=True,
        format_text=True,
        sentiment_analysis=True,      # AssemblyAI built-in sentiment
        auto_highlights=True,         # Key topics detection
    )

    console.print("[cyan]→ Uploading audio to AssemblyAI...[/cyan]")
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_path, config=config)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"Transcription failed: {transcript.error}")

    console.print(f"[green]✓ Transcription complete — {len(transcript.words)} words detected[/green]")
    return transcript


def format_transcript_for_analysis(transcript) -> tuple[str, dict]:
    """
    Convert AssemblyAI transcript to clean labeled text for Claude.
    Returns (formatted_text, speaker_word_counts)
    """
    speaker_map = {}      # Map AssemblyAI speaker IDs to clean labels
    label_counter = ord('A')
    formatted_lines = []
    word_counts = {}

    for utterance in transcript.utterances:
        speaker_raw = utterance.speaker
        if speaker_raw not in speaker_map:
            speaker_map[speaker_raw] = f"Speaker {chr(label_counter)}"
            label_counter += 1

        label = speaker_map[speaker_raw]
        text = utterance.text.strip()
        formatted_lines.append(f"{label}: {text}")

        # Count words per speaker
        words = len(text.split())
        word_counts[label] = word_counts.get(label, 0) + words

    formatted_text = "\n".join(formatted_lines)
    return formatted_text, word_counts, speaker_map


def load_transcript_file(path: str) -> tuple[str, dict]:
    """
    Load a pre-existing transcript file (skip AssemblyAI step).
    Expects format: 'Speaker A: ...' per line.
    """
    text = Path(path).read_text(encoding="utf-8")
    word_counts = {}
    for line in text.strip().split("\n"):
        if ":" in line:
            parts = line.split(":", 1)
            speaker = parts[0].strip()
            words = len(parts[1].strip().split())
            word_counts[speaker] = word_counts.get(speaker, 0) + words
    return text, word_counts, {}


# ─────────────────────────────────────────────
# 2. CLAUDE API — Psychological Analysis
# ─────────────────────────────────────────────

def analyze_psychology(transcript_text: str, context: str = "professional meeting") -> dict:
    """
    Send formatted transcript to Claude for psychological profiling.
    Returns structured JSON profile.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY not set in .env")

    user_message = build_user_prompt(transcript_text, context)

    console.print("[cyan]→ Sending to Claude for psychological analysis...[/cyan]")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    raw_response = message.content[0].text.strip()

    # Strip markdown fences if Claude added them anyway
    if raw_response.startswith("```"):
        raw_response = raw_response.split("```")[1]
        if raw_response.startswith("json"):
            raw_response = raw_response[4:]
        raw_response = raw_response.strip()

    try:
        result = json.loads(raw_response)
        console.print("[green]✓ Psychological analysis complete[/green]")
        return result
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON parse error: {e}[/red]")
        console.print("[yellow]Raw response saved to debug_response.txt[/yellow]")
        Path("debug_response.txt").write_text(raw_response)
        raise


# ─────────────────────────────────────────────
# 3. REPORT GENERATOR
# ─────────────────────────────────────────────

def generate_report(analysis: dict, output_path: str = "report.json") -> None:
    """
    Save full JSON report and print a human-readable summary to console.
    """
    # Save full JSON
    Path(output_path).write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    console.print(f"[green]✓ Full JSON report saved → {output_path}[/green]\n")

    # Console summary
    meta = analysis.get("session_metadata", {})
    console.print(Panel(
        f"[bold]Speakers:[/bold] {meta.get('speaker_count', '?')} | "
        f"[bold]Words:[/bold] {meta.get('total_word_count', '?')} | "
        f"[bold]Confidence:[/bold] {meta.get('analysis_confidence', '?')}\n"
        f"[bold]Group tension:[/bold] {meta.get('overall_group_tension', '?')}/10 | "
        f"[bold]Cohesion:[/bold] {meta.get('group_cohesion', '?')}/10",
        title="[bold cyan]Session Overview[/bold cyan]",
        border_style="cyan"
    ))

    for speaker in analysis.get("speakers", []):
        sid = speaker["speaker_id"]
        bf = speaker.get("big_five", {})
        em = speaker.get("emotional_state", {})
        cs = speaker.get("communication_style", {})
        flags = speaker.get("risk_flags", {})

        flag_str = ""
        if flags.get("elevated_anxiety"):     flag_str += "⚠ Anxiety  "
        if flags.get("social_withdrawal"):    flag_str += "⚠ Withdrawal  "
        if flags.get("potential_conflict"):   flag_str += "⚠ Conflict  "
        if flags.get("disengagement"):        flag_str += "⚠ Disengaged  "
        if not flag_str:                      flag_str = "✓ No flags"

        big5_bar = (
            f"O:{bf.get('openness',{}).get('score','?'):>3}  "
            f"C:{bf.get('conscientiousness',{}).get('score','?'):>3}  "
            f"E:{bf.get('extraversion',{}).get('score','?'):>3}  "
            f"A:{bf.get('agreeableness',{}).get('score','?'):>3}  "
            f"N:{bf.get('neuroticism',{}).get('score','?'):>3}"
        )

        console.print(Panel(
            f"[bold]Words:[/bold] {speaker.get('word_count','?')} | "
            f"[bold]Confidence:[/bold] {speaker.get('confidence','?')}\n\n"
            f"[bold]Big Five (OCEAN):[/bold]\n{big5_bar}\n\n"
            f"[bold]Dominant emotion:[/bold] {em.get('dominant_emotion','?')} | "
            f"[bold]Style:[/bold] {cs.get('style','?')}\n\n"
            f"[bold]Risk flags:[/bold] {flag_str}\n\n"
            f"[italic]{speaker.get('summary','')}[/italic]",
            title=f"[bold magenta]{sid}[/bold magenta]",
            border_style="magenta"
        ))

    gd = analysis.get("group_dynamics", {})
    if gd:
        console.print(Panel(
            f"[bold]Power structure:[/bold] {gd.get('power_structure','?')}\n"
            f"[bold]Dominant speaker:[/bold] {gd.get('dominant_speaker','?')}\n"
            f"[bold]Most collaborative:[/bold] {gd.get('most_collaborative','?')}\n"
            f"[bold]Most at risk:[/bold] {gd.get('most_at_risk','?')}\n\n"
            f"[italic]{gd.get('group_summary','')}[/italic]",
            title="[bold yellow]Group Dynamics[/bold yellow]",
            border_style="yellow"
        ))


# ─────────────────────────────────────────────
# 4. CLI ENTRYPOINT
# ─────────────────────────────────────────────

@app.command()
def run(
    audio: str = typer.Option(None, "--audio", "-a", help="Path to audio file (.m4a, .mp3, .wav)"),
    transcript: str = typer.Option(None, "--transcript", "-t", help="Path to pre-existing transcript .txt"),
    context: str = typer.Option("professional meeting", "--context", "-c", help="Context description"),
    output: str = typer.Option("report.json", "--output", "-o", help="Output JSON file path"),
):
    """
    PsychoMeet MVP — Multi-speaker psychological analysis pipeline.
    Provide either --audio or --transcript.
    """
    console.print(Panel("[bold]PsychoMeet MVP[/bold] — Psychological Analysis Pipeline",
                        border_style="blue"))

    if not audio and not transcript:
        console.print("[red]Error: provide --audio or --transcript[/red]")
        raise typer.Exit(1)

    transcript_text = None
    word_counts = {}

    if audio:
        if not Path(audio).exists():
            console.print(f"[red]Audio file not found: {audio}[/red]")
            raise typer.Exit(1)
        aai_transcript = transcribe_audio(audio)
        transcript_text, word_counts, speaker_map = format_transcript_for_analysis(aai_transcript)
        # Save formatted transcript for reference
        Path("transcript.txt").write_text(transcript_text, encoding="utf-8")
        console.print("[dim]→ Formatted transcript saved to transcript.txt[/dim]")

    elif transcript:
        if not Path(transcript).exists():
            console.print(f"[red]Transcript file not found: {transcript}[/red]")
            raise typer.Exit(1)
        transcript_text, word_counts, _ = load_transcript_file(transcript)

    console.print(f"\n[dim]Word counts per speaker: {word_counts}[/dim]\n")

    # Run psychological analysis
    analysis = analyze_psychology(transcript_text, context)

    # Generate report
    generate_report(analysis, output)

    console.print(f"\n[bold green]✓ Pipeline complete.[/bold green] Report: [cyan]{output}[/cyan]")


if __name__ == "__main__":
    app()
