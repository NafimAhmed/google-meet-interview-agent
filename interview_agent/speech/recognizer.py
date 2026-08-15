"""Faster Whisper speech recognition."""

from typing import Any, Optional

from faster_whisper import WhisperModel

from interview_agent.audio.recorder import AudioRecorder
from interview_agent.config import Settings
from interview_agent.utils import clean_text


class SpeechRecognizer:
    def __init__(self, config: Settings, recorder: AudioRecorder) -> None:
        self.config = config
        self.recorder = recorder
        self._model: Optional[Any] = None

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        print("\nLoading speech recognition model...")
        print("First run e model download hote pare.\n")
        try:
            self._model = WhisperModel(
                self.config.stt_model_name,
                device="cpu",
                compute_type="int8",
            )
            print("✅ Speech recognition model ready.")
            return True
        except Exception as error:
            print(f"❌ Speech model load error: {error}")
            print("CMD te run koro: py -m pip install faster-whisper")
            self._model = None
            return False

    def transcribe(self, file_name: str, language: str) -> str:
        if self._model is None:
            return "TRANSCRIPTION_ERROR: Speech model load hoy nai."

        language_code = None
        normalized_language = clean_text(language).lower()
        if "bangla" in normalized_language or "bengali" in normalized_language:
            language_code = "bn"
        elif "english" in normalized_language:
            language_code = "en"

        try:
            segments, _ = self._model.transcribe(
                file_name,
                language=language_code,
                beam_size=5,
                vad_filter=True,
            )
            return " ".join(
                segment.text.strip() for segment in segments
            ).strip()
        except Exception as error:
            return f"TRANSCRIPTION_ERROR: {error}"

    def listen(self, language: str, seconds: int) -> str:
        if not self.recorder.capture_after_beep(seconds):
            return ""
        print("\n🧠 Voice theke text banano hocche...")
        text = self.transcribe(self.config.temp_audio_file, language)
        print(f"\n🗣️ Candidate said: {text}\n")
        return text
