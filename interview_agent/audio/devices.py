"""Windows audio-device discovery and setup diagnostics."""

from typing import Optional

import sounddevice as sd

from interview_agent.config import Settings
from interview_agent.utils import clean_text

try:
    import winsound
except ImportError:  # pragma: no cover - available only on Windows
    winsound = None


def print_audio_devices() -> None:
    print("\n==============================")
    print("SoundDevice Audio Devices")
    print("==============================")
    try:
        for index, device in enumerate(sd.query_devices()):
            name = device.get("name", "")
            max_input = device.get("max_input_channels", 0)
            max_output = device.get("max_output_channels", 0)
            print(
                f"{index}: {name} | input={max_input} | output={max_output}"
            )
    except Exception as error:
        print(f"Audio device list error: {error}")


def find_input_device_id(keyword: str) -> Optional[int]:
    normalized_keyword = clean_text(keyword).lower()
    if not normalized_keyword:
        return None

    try:
        for index, device in enumerate(sd.query_devices()):
            name = clean_text(device.get("name", "")).lower()
            max_input = int(device.get("max_input_channels", 0))
            if normalized_keyword in name and max_input > 0:
                return index
    except Exception:
        return None
    return None


def check_audio_setup(config: Settings) -> None:
    print_audio_devices()
    print("\n==============================")
    print("Required Audio Setup")
    print("==============================")
    print("Windows Playback Default = CABLE Input")
    print(f"Google Meet Microphone  = {config.meet_mic_device_name}")
    print(f"Google Meet Speaker     = {config.meet_speaker_device_name}")
    print(f"Python STT Input        = {config.python_stt_input_keyword}")

    stt_device_id = find_input_device_id(config.python_stt_input_keyword)
    if stt_device_id is None:
        print(
            f"\n❌ Python STT input found hoy nai: "
            f"{config.python_stt_input_keyword}"
        )
        print(
            "Win + R -> mmsys.cpl -> Recording tab e CABLE Out 16ch "
            "enabled ache kina check koro."
        )
    else:
        print(
            f"\n✅ Python STT input found: {config.python_stt_input_keyword} "
            f"| device id={stt_device_id}"
        )

    print("\nTTS voice Windows default Playback device diye jabe.")
    print("Tai Windows Playback default অবশ্যই CABLE Input korte hobe.")


def play_start_beep() -> None:
    try:
        if winsound:
            winsound.Beep(1000, 250)
        else:
            print("\a")
    except Exception:
        print("\a")
