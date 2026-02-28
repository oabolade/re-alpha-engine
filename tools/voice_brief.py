"""Skill 4: Voice Brief Generator — produces audio narration of the investment memo executive summary.

Supports OpenAI TTS (primary) and ElevenLabs (fallback).
"""

import anthropic
import openai

from config import ANTHROPIC_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY, CLAUDE_MODEL

# OpenAI TTS voices — professional options
VOICE_OPTIONS = {
    "onyx": "onyx",           # Deep, authoritative male
    "nova": "nova",           # Warm, professional female
    "echo": "echo",           # Clear, neutral male
    "shimmer": "shimmer",     # Expressive female
}

DEFAULT_VOICE = "onyx"


BRIEF_SYSTEM_PROMPT = """You are an institutional investment analyst preparing a 45-second spoken voice brief.

Convert the provided investment memo into a concise spoken summary suitable for audio narration.

Rules:
- Maximum 120 words (approximately 45 seconds when spoken).
- Lead with the property name, location, and verdict (GO/NO-GO/CONDITIONAL).
- State 2-3 key financial metrics (NOI, cap rate, IRR if available).
- Mention the single most important risk and the single biggest upside.
- End with a clear recommended action.
- Write in natural spoken language — no bullet points, no tables, no markdown.
- Use professional, confident tone. No filler words.
- Do not include emojis or special characters.
- Write as if speaking directly to an investment committee."""


def generate_voice_brief_text(memo: str) -> str:
    """Condense the full memo into a 45-second spoken brief using Claude."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        system=BRIEF_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Investment memo to summarize:\n\n{memo}"}],
    )

    return response.content[0].text


def synthesize_audio(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Convert text to speech. Uses OpenAI TTS (primary) or ElevenLabs (fallback)."""
    if OPENAI_API_KEY:
        return _synthesize_openai(text, voice)
    if ELEVENLABS_API_KEY:
        return _synthesize_elevenlabs(text, voice)
    raise RuntimeError("No TTS API key configured. Set OPENAI_API_KEY or ELEVENLABS_API_KEY.")


def _synthesize_openai(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Convert text to speech using OpenAI TTS. Returns MP3 audio bytes."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    voice_name = VOICE_OPTIONS.get(voice, DEFAULT_VOICE)

    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=voice_name,
        input=text,
        response_format="mp3",
    )

    return response.content


def _synthesize_elevenlabs(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Fallback: Convert text to speech using ElevenLabs."""
    from elevenlabs import ElevenLabs

    elevenlabs_voices = {
        "onyx": "TX3LPaxmHKxFdv7VOQHJ",       # Map to Liam
        "nova": "XB0fDUnXU5powFXDhCwa",        # Map to Charlotte
        "echo": "TX3LPaxmHKxFdv7VOQHJ",
        "shimmer": "XB0fDUnXU5powFXDhCwa",
    }

    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    voice_id = elevenlabs_voices.get(voice, elevenlabs_voices["onyx"])

    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
    )

    return b"".join(audio_generator)


def generate_voice_brief(memo: str, voice: str = DEFAULT_VOICE) -> tuple[str, bytes]:
    """Full pipeline: memo → spoken brief text → audio bytes.

    Returns (brief_text, audio_bytes).
    """
    brief_text = generate_voice_brief_text(memo)
    audio_bytes = synthesize_audio(brief_text, voice)
    return brief_text, audio_bytes
