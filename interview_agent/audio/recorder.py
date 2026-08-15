"""Candidate audio recording service."""

import time
import wave

import sounddevice as sd

from interview_agent.audio.devices import find_input_device_id, play_start_beep
from interview_agent.config import Settings


class AudioRecorder:
    def __init__(self, config: Settings) -> None:
        self.config = config

    def record(self, file_name: str, seconds: int) -> bool:
        try:
            device_id = find_input_device_id(
                self.config.python_stt_input_keyword
            )
            print("\n🎙️ Listening started...")
            print(f"Recording time: {seconds} seconds.")

            if device_id is None:
                print(
                    f"❌ Input device found hoy nai: "
                    f"{self.config.python_stt_input_keyword}"
                )
                print("Recording tab e CABLE Out 16ch ache kina check koro.")
                return False

            print(
                f"✅ Recording from: {self.config.python_stt_input_keyword} "
                f"| id={device_id}"
            )
            audio = sd.rec(
                int(seconds * self.config.sample_rate),
                samplerate=self.config.sample_rate,
                channels=1,
                dtype="int16",
                device=device_id,
            )
            sd.wait()

            with wave.open(file_name, "wb") as wave_file:
                wave_file.setnchannels(1)
                wave_file.setsampwidth(2)
                wave_file.setframerate(self.config.sample_rate)
                wave_file.writeframes(audio.tobytes())

            print("✅ Listening finished.")
            return True
        except Exception as error:
            print(f"❌ Recording error: {error}")
            return False

    def capture_after_beep(self, seconds: int) -> bool:
        print(
            f"\n⏳ Recording will start in "
            f"{self.config.auto_record_delay_seconds} second..."
        )
        time.sleep(self.config.auto_record_delay_seconds)
        play_start_beep()
        return self.record(self.config.temp_audio_file, seconds)
