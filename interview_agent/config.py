"""Central application configuration.

Every setting can be overridden with an environment variable. The defaults match
the values used by the original single-file application.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings shared by all application services."""

    ai_agent_email: str = field(
        default_factory=lambda: os.getenv(
            "AI_AGENT_EMAIL", "recent.eagleeye@gmail.com"
        )
    )
    chrome_profile_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("GOOGLE_CHROME_PROFILE_DIR", "ai_meet_chrome_profile")
        ).resolve()
    )
    meet_mic_device_name: str = field(
        default_factory=lambda: os.getenv("MEET_MIC_DEVICE_NAME", "CABLE Output")
    )
    meet_speaker_device_name: str = field(
        default_factory=lambda: os.getenv(
            "MEET_SPEAKER_DEVICE_NAME", "CABLE In 16ch"
        )
    )
    python_stt_input_keyword: str = field(
        default_factory=lambda: os.getenv(
            "PYTHON_STT_INPUT_KEYWORD", "CABLE Out 16ch"
        )
    )

    ollama_base_url: str = field(
        default_factory=lambda: os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        ).rstrip("/")
    )
    llm_model_name: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL_NAME", "qwen2.5:3b")
    )
    stt_model_name: str = field(
        default_factory=lambda: os.getenv("STT_MODEL_NAME", "base")
    )

    audio_seconds: int = field(
        default_factory=lambda: _env_int("AUDIO_SECONDS", 15)
    )
    confirmation_audio_seconds: int = field(
        default_factory=lambda: _env_int("CONFIRMATION_AUDIO_SECONDS", 5)
    )
    auto_record_delay_seconds: float = field(
        default_factory=lambda: _env_float("AUTO_RECORD_DELAY_SECONDS", 1.0)
    )
    sample_rate: int = field(
        default_factory=lambda: _env_int("SAMPLE_RATE", 16000)
    )
    temp_audio_file: str = field(
        default_factory=lambda: os.getenv(
            "TEMP_AUDIO_FILE", "candidate_answer.wav"
        )
    )
    request_timeout: int = field(
        default_factory=lambda: _env_int("REQUEST_TIMEOUT", 180)
    )
    bangla_voice: str = field(
        default_factory=lambda: os.getenv(
            "BANGLA_VOICE", "bn-BD-NabanitaNeural"
        )
    )
    english_voice: str = field(
        default_factory=lambda: os.getenv(
            "ENGLISH_VOICE", "en-US-AriaNeural"
        )
    )

    @property
    def ollama_generate_url(self) -> str:
        return f"{self.ollama_base_url}/api/generate"


settings = Settings()
