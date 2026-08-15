"""Edge TTS with Windows SAPI fallback."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import edge_tts

from interview_agent.config import Settings
from interview_agent.utils import clean_text, has_bangla, powershell_quote


class TextToSpeech:
    def __init__(self, config: Settings) -> None:
        self.config = config

    def _voice_for(self, text: str, language: str = "") -> str:
        normalized_language = clean_text(language).lower()
        if (
            has_bangla(clean_text(text))
            or "bangla" in normalized_language
            or "bengali" in normalized_language
        ):
            return self.config.bangla_voice
        return self.config.english_voice

    @staticmethod
    def _estimated_wait(text: str) -> int:
        return max(5, min(90, int(len(clean_text(text)) / 11) + 4))

    @staticmethod
    def _play_mp3(mp3_path: str, wait_seconds: int) -> bool:
        try:
            uri = Path(mp3_path).resolve().as_uri()
            script = f"""
Add-Type -AssemblyName PresentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$player.Volume = 1.0
$player.Open([System.Uri]{powershell_quote(uri)})
Start-Sleep -Milliseconds 1200
$player.Play()
Start-Sleep -Seconds {wait_seconds}
$player.Stop()
$player.Close()
"""
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-STA",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=wait_seconds + 15,
                check=False,
            )
            return result.returncode == 0
        except Exception as error:
            print(f"❌ PowerShell MP3 play error: {error}")
            return False

    @staticmethod
    def _sapi_fallback(text: str) -> None:
        temp_text_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".txt",
                mode="w",
                encoding="utf-8",
            ) as temp_file:
                temp_text_path = temp_file.name
                temp_file.write(text)

            script = f"""
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.Volume = 100
$speaker.Rate = 0
$text = Get-Content -Raw -Encoding UTF8 {powershell_quote(temp_text_path)}
$speaker.Speak($text)
$speaker.Dispose()
"""
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=90,
                check=False,
            )
        except Exception as error:
            print(f"❌ SAPI fallback error: {error}")
        finally:
            try:
                if temp_text_path and os.path.exists(temp_text_path):
                    os.remove(temp_text_path)
            except OSError:
                pass

    async def _edge_speak(self, text: str, language: str = "") -> None:
        normalized_text = clean_text(text)
        if not normalized_text:
            return

        temp_audio_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".mp3"
            ) as temp_file:
                temp_audio_path = temp_file.name

            communicate = edge_tts.Communicate(
                text=normalized_text,
                voice=self._voice_for(normalized_text, language),
                rate="+0%",
                volume="+0%",
            )
            await communicate.save(temp_audio_path)

            if not self._play_mp3(
                temp_audio_path, self._estimated_wait(normalized_text)
            ):
                print("⚠️ Edge MP3 play failed. Windows SAPI fallback use hocche.")
                self._sapi_fallback(normalized_text)
        except Exception as error:
            print(f"❌ TTS_ERROR: {error}")
            print("Windows SAPI fallback use hocche.")
            self._sapi_fallback(normalized_text)
        finally:
            try:
                if temp_audio_path and os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
            except OSError:
                pass

    def speak(self, text: str, language: str = "") -> None:
        normalized_text = clean_text(text)
        if not normalized_text:
            return

        print(f"\n🤖 Agent: {normalized_text}\n")
        try:
            asyncio.run(self._edge_speak(normalized_text, language))
        except Exception as error:
            print(f"❌ SPEAK_ERROR: {error}")
            self._sapi_fallback(normalized_text)
