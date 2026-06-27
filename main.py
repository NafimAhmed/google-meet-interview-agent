

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import edge_tts
import requests
import sounddevice as sd
from faster_whisper import WhisperModel

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

try:
    import winsound
except Exception:
    winsound = None


# =============================
# Console Unicode Fix
# =============================

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass


# =============================
# GOOGLE MEET + AUDIO CONFIG
# =============================

AI_AGENT_EMAIL = "recent.eagleeye@gmail.com"
GOOGLE_CHROME_PROFILE_DIR = os.path.abspath("ai_meet_chrome_profile")

# Google Meet e exactly eta select korba:
MEET_MIC_DEVICE_NAME = "CABLE Output"
MEET_SPEAKER_DEVICE_NAME = "CABLE In 16ch"

# Candidate voice record korar jonno:
PYTHON_STT_INPUT_KEYWORD = "CABLE Out 16ch"

# IMPORTANT:
# Windows Playback Default Device = CABLE Input korte hobe.
# TTS voice PowerShell/Windows default output diye play hobe.


# =============================
# AI CONFIG
# =============================

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"

LLM_MODEL_NAME = "qwen2.5:3b"
STT_MODEL_NAME = "base"

AUDIO_SECONDS = 15
CONFIRMATION_AUDIO_SECONDS = 5
AUTO_RECORD_DELAY_SECONDS = 1.0

SAMPLE_RATE = 16000
TEMP_AUDIO_FILE = "candidate_answer.wav"
REQUEST_TIMEOUT = 180

BANGLA_VOICE = "bn-BD-NabanitaNeural"
ENGLISH_VOICE = "en-US-AriaNeural"

_playwright_instance = None
_meet_context = None
_meet_page = None


# =============================
# COMMON HELPERS
# =============================

def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def has_bangla(text: str) -> bool:
    return any("\u0980" <= ch <= "\u09FF" for ch in text)


def get_tts_voice(text: str, language: str = "") -> str:
    text = clean_text(text)
    language = clean_text(language).lower()

    if has_bangla(text) or "bangla" in language or "bengali" in language:
        return BANGLA_VOICE

    return ENGLISH_VOICE


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    text = clean_text(value).lower()
    return text in ["true", "yes", "y", "1", "needed"]


def parse_score(value: Any) -> int:
    if isinstance(value, (int, float)):
        score = int(value)
    else:
        text = clean_text(value)
        match = re.search(r"\d+", text)
        score = int(match.group()) if match else 0

    if score < 0:
        return 0
    if score > 10:
        return 10

    return score


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = clean_text(text)

    if not text:
        return None

    text = text.replace("```json", "")
    text = text.replace("```JSON", "")
    text = text.replace("```", "")
    text = text.strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    try:
        start = text.find("{")
        end = text.rfind("}") + 1

        if start == -1 or end <= start:
            return None

        json_text = text[start:end]
        data = json.loads(json_text)

        if isinstance(data, dict):
            return data

        return None
    except Exception:
        return None


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def play_start_beep() -> None:
    try:
        if winsound:
            winsound.Beep(1000, 250)
        else:
            print("\a")
    except Exception:
        print("\a")


def normalize_command_text(text: str) -> str:
    text = clean_text(text).lower()
    text = re.sub(r"[^a-zA-Z0-9\u0980-\u09FF\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_start_command(text: str) -> bool:
    text = normalize_command_text(text)

    start_words = [
        "yes",
        "ok",
        "okay",
        "start",
        "ready",
        "i am ready",
        "i'm ready",
        "begin",
        "go",
        "হ্যাঁ",
        "হ্যা",
        "আচ্ছা",
        "শুরু",
        "শুরু করুন",
        "আমি প্রস্তুত",
    ]

    return any(word in text for word in start_words)


def is_skip_command(text: str) -> bool:
    text = normalize_command_text(text)

    skip_words = [
        "skip",
        "next",
        "next question",
        "next question please",
        "i don't know",
        "i dont know",
        "i can't answer",
        "i cant answer",
        "i cannot answer",
        "no idea",
        "pass",
        "বাদ",
        "পরের প্রশ্ন",
        "জানি না",
        "আমি জানি না",
        "উত্তর দিতে পারবো না",
        "স্কিপ",
    ]

    return any(word in text for word in skip_words)


# =============================
# AUDIO DEVICE HELPERS
# =============================

def print_audio_devices() -> None:
    print("\n==============================")
    print("SoundDevice Audio Devices")
    print("==============================")

    try:
        devices = sd.query_devices()

        for index, device in enumerate(devices):
            name = device.get("name", "")
            max_in = device.get("max_input_channels", 0)
            max_out = device.get("max_output_channels", 0)
            print(f"{index}: {name} | input={max_in} | output={max_out}")

    except Exception as e:
        print(f"Audio device list error: {e}")


def find_input_device_id(keyword: str) -> Optional[int]:
    keyword = clean_text(keyword).lower()

    if not keyword:
        return None

    try:
        devices = sd.query_devices()

        for index, device in enumerate(devices):
            name = clean_text(device.get("name", "")).lower()
            max_in = int(device.get("max_input_channels", 0))

            if keyword in name and max_in > 0:
                return index

        return None

    except Exception:
        return None


def check_audio_setup() -> None:
    print_audio_devices()

    print("\n==============================")
    print("Required Audio Setup")
    print("==============================")
    print("Windows Playback Default = CABLE Input")
    print(f"Google Meet Microphone  = {MEET_MIC_DEVICE_NAME}")
    print(f"Google Meet Speaker     = {MEET_SPEAKER_DEVICE_NAME}")
    print(f"Python STT Input        = {PYTHON_STT_INPUT_KEYWORD}")

    stt_id = find_input_device_id(PYTHON_STT_INPUT_KEYWORD)

    if stt_id is None:
        print(f"\n❌ Python STT input found hoy nai: {PYTHON_STT_INPUT_KEYWORD}")
        print("Win + R -> mmsys.cpl -> Recording tab e CABLE Out 16ch enabled ache kina check koro.")
    else:
        print(f"\n✅ Python STT input found: {PYTHON_STT_INPUT_KEYWORD} | device id={stt_id}")

    print("\nTTS voice Windows default Playback device diye jabe.")
    print("Tai Windows Playback default অবশ্যই CABLE Input korte hobe.")


# =============================
# GOOGLE MEET AUTOMATION
# =============================

def normalize_meet_url(value: str) -> str:
    value = clean_text(value)

    if not value:
        return ""

    if value.startswith("http://") or value.startswith("https://"):
        return value

    value = value.replace("meet.google.com/", "").strip("/")
    return f"https://meet.google.com/{value}"


def safe_click_meet_button(page, pattern: str, timeout: int = 5000) -> bool:
    try:
        page.get_by_role("button", name=re.compile(pattern, re.I)).click(timeout=timeout)
        return True
    except Exception:
        return False


def open_google_meet(meet_url: str) -> bool:
    global _playwright_instance, _meet_context, _meet_page

    meet_url = normalize_meet_url(meet_url)

    if not meet_url:
        print("Google Meet link empty.")
        return False

    if sync_playwright is None:
        print("\n❌ Playwright installed na.")
        print("CMD te run koro:")
        print("py -m pip install playwright")
        print("py -m playwright install")
        return False

    print("\n==============================")
    print("Opening Google Meet")
    print("==============================")
    print(f"AI account: {AI_AGENT_EMAIL}")
    print(f"Meet URL: {meet_url}")
    print(f"Chrome profile: {GOOGLE_CHROME_PROFILE_DIR}")

    try:
        _playwright_instance = sync_playwright().start()

        launch_args = [
            "--use-fake-ui-for-media-stream",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--start-maximized",
        ]

        try:
            _meet_context = _playwright_instance.chromium.launch_persistent_context(
                user_data_dir=GOOGLE_CHROME_PROFILE_DIR,
                channel="chrome",
                headless=False,
                args=launch_args,
                viewport=None,
            )
        except Exception:
            _meet_context = _playwright_instance.chromium.launch_persistent_context(
                user_data_dir=GOOGLE_CHROME_PROFILE_DIR,
                headless=False,
                args=launch_args,
                viewport=None,
            )

        try:
            _meet_context.grant_permissions(
                ["microphone", "camera"],
                origin="https://meet.google.com",
            )
        except Exception:
            pass

        _meet_page = _meet_context.new_page()
        _meet_page.goto(meet_url, wait_until="domcontentloaded", timeout=60000)

        time.sleep(5)

        safe_click_meet_button(_meet_page, r"Got it|Dismiss|Close|Allow", timeout=3000)
        safe_click_meet_button(_meet_page, r"Turn off camera", timeout=3000)

        joined = False

        join_patterns = [
            r"Join now",
            r"Ask to join",
            r"Request to join",
            r"Join",
        ]

        for pattern in join_patterns:
            if safe_click_meet_button(_meet_page, pattern, timeout=8000):
                joined = True
                break

        if joined:
            print("✅ Join button clicked.")
            print("Host accept lagle host-ke accept korte hobe.")
        else:
            print("⚠️ Auto join click hoy nai. Browser e manually Join / Ask to join click koro.")

        print("\nMeet Settings > Audio e eta set koro:")
        print(f"Microphone = {MEET_MIC_DEVICE_NAME}")
        print(f"Speaker    = {MEET_SPEAKER_DEVICE_NAME}")
        print("Mic unmute rakhba.")

        input("\nMeet setup complete hole ENTER press koro... ")

        return True

    except Exception as e:
        print(f"❌ Google Meet open error: {e}")
        return False


def close_google_meet() -> None:
    global _playwright_instance, _meet_context, _meet_page

    try:
        if _meet_context:
            _meet_context.close()
    except Exception:
        pass

    try:
        if _playwright_instance:
            _playwright_instance.stop()
    except Exception:
        pass

    _playwright_instance = None
    _meet_context = None
    _meet_page = None


# =============================
# TTS FIXED: EDGE TTS MP3 + POWERSHELL PLAYER
# =============================

def estimate_tts_wait_seconds(text: str) -> int:
    text = clean_text(text)

    seconds = int(len(text) / 11) + 4

    if seconds < 5:
        return 5
    if seconds > 90:
        return 90

    return seconds


def play_mp3_on_windows_default_output(mp3_path: str, wait_seconds: int) -> bool:
    """
    Windows default playback device use kore MP3 play kore.
    Default playback device jodi CABLE Input hoy,
    tahole voice Google Meet microphone CABLE Output e jabe.
    """

    try:
        uri = Path(mp3_path).resolve().as_uri()

        ps_script = f"""
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
                ps_script,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=wait_seconds + 15,
        )

        return result.returncode == 0

    except Exception as e:
        print(f"❌ PowerShell MP3 play error: {e}")
        return False


def speak_with_windows_sapi_fallback(text: str) -> None:
    """
    Edge MP3 play fail korle Windows built-in voice diye speak korbe.
    Eta default playback device use kore.
    """

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

        ps_script = f"""
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
                ps_script,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=90,
        )

    except Exception as e:
        print(f"❌ SAPI fallback error: {e}")

    finally:
        try:
            if temp_text_path and os.path.exists(temp_text_path):
                os.remove(temp_text_path)
        except Exception:
            pass


async def edge_speak_async(text: str, language: str = "") -> None:
    text = clean_text(text)

    if not text:
        return

    voice = get_tts_voice(text, language)
    temp_audio_path = ""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_audio_path = temp_file.name

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate="+0%",
            volume="+0%",
        )

        await communicate.save(temp_audio_path)

        wait_seconds = estimate_tts_wait_seconds(text)

        played = play_mp3_on_windows_default_output(
            mp3_path=temp_audio_path,
            wait_seconds=wait_seconds,
        )

        if not played:
            print("⚠️ Edge MP3 play failed. Windows SAPI fallback use hocche.")
            speak_with_windows_sapi_fallback(text)

    except Exception as e:
        print(f"❌ TTS_ERROR: {e}")
        print("Windows SAPI fallback use hocche.")
        speak_with_windows_sapi_fallback(text)

    finally:
        try:
            if temp_audio_path and os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except Exception:
            pass


def speak(text: str, language: str = "") -> None:
    text = clean_text(text)

    if not text:
        return

    print(f"\n🤖 Agent: {text}\n")

    try:
        asyncio.run(edge_speak_async(text, language))
    except Exception as e:
        print(f"❌ SPEAK_ERROR: {e}")
        speak_with_windows_sapi_fallback(text)


# =============================
# OLLAMA
# =============================

def ollama_is_running() -> bool:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def installed_models() -> List[str]:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        models = data.get("models", [])

        return [item.get("name", "") for item in models if item.get("name")]
    except Exception:
        return []


def model_is_installed(model_name: str) -> bool:
    models = installed_models()
    return model_name in models


def ask_ai(prompt: str, json_mode: bool = False) -> str:
    payload: Dict[str, Any] = {
        "model": LLM_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
        },
    }

    if json_mode:
        payload["format"] = "json"

    try:
        response = requests.post(
            OLLAMA_GENERATE_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            return f"OLLAMA_ERROR: {response.text}"

        data = response.json()
        return clean_text(data.get("response", ""))

    except requests.exceptions.ConnectionError:
        return "OLLAMA_CONNECTION_ERROR: Ollama server running na."

    except requests.exceptions.Timeout:
        return "OLLAMA_TIMEOUT_ERROR: Model response dite beshi time nicche."

    except Exception as e:
        return f"PYTHON_ERROR: {str(e)}"


# =============================
# STT
# =============================

def load_stt_model():
    print("\nLoading speech recognition model...")
    print("First run e model download hote pare.\n")

    try:
        model = WhisperModel(
            STT_MODEL_NAME,
            device="cpu",
            compute_type="int8",
        )

        print("✅ Speech recognition model ready.")
        return model

    except Exception as e:
        print(f"❌ Speech model load error: {e}")
        print("CMD te run koro: py -m pip install faster-whisper")
        return None


stt_model = load_stt_model()


def record_audio(file_name: str, seconds: int = AUDIO_SECONDS) -> bool:
    try:
        input_device_id = find_input_device_id(PYTHON_STT_INPUT_KEYWORD)

        print("\n🎙️ Listening started...")
        print(f"Recording time: {seconds} seconds.")

        if input_device_id is None:
            print(f"❌ Input device found hoy nai: {PYTHON_STT_INPUT_KEYWORD}")
            print("Recording tab e CABLE Out 16ch ache kina check koro.")
            return False

        print(f"✅ Recording from: {PYTHON_STT_INPUT_KEYWORD} | id={input_device_id}")

        audio = sd.rec(
            int(seconds * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            device=input_device_id,
        )

        sd.wait()

        with wave.open(file_name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())

        print("✅ Listening finished.")
        return True

    except Exception as e:
        print(f"❌ Recording error: {e}")
        return False


def transcribe_audio(file_name: str, language: str) -> str:
    if stt_model is None:
        return "TRANSCRIPTION_ERROR: Speech model load hoy nai."

    lang = None
    language_lower = clean_text(language).lower()

    if "bangla" in language_lower or "bengali" in language_lower:
        lang = "bn"
    elif "english" in language_lower:
        lang = "en"

    try:
        segments, info = stt_model.transcribe(
            file_name,
            language=lang,
            beam_size=5,
            vad_filter=True,
        )

        text_parts = []

        for segment in segments:
            text_parts.append(segment.text.strip())

        return " ".join(text_parts).strip()

    except Exception as e:
        return f"TRANSCRIPTION_ERROR: {str(e)}"


def listen_answer_auto(language: str, seconds: int = AUDIO_SECONDS) -> str:
    print(f"\n⏳ Recording will start in {AUTO_RECORD_DELAY_SECONDS} second...")
    time.sleep(AUTO_RECORD_DELAY_SECONDS)

    play_start_beep()

    is_recorded = record_audio(TEMP_AUDIO_FILE, seconds)

    if not is_recorded:
        return ""

    print("\n🧠 Voice theke text banano hocche...")
    text = transcribe_audio(TEMP_AUDIO_FILE, language)

    print(f"\n🗣️ Candidate said: {text}\n")

    return text


def wait_for_candidate_start(language: str) -> None:
    speak("Interview is ready. Please say yes or ok to start.", language)

    for attempt in range(1, 4):
        print(f"\nStart confirmation attempt {attempt}/3")
        answer = listen_answer_auto(language, seconds=CONFIRMATION_AUDIO_SECONDS)

        if is_start_command(answer):
            speak("Great. Interview started.", language)
            return

        speak("I could not understand. Please say yes or ok to start.", language)

    print("⚠️ Start confirmation clear na. Interview auto start hocche.")
    speak("I will start the interview now.", language)


# =============================
# INTERVIEW AI FUNCTIONS
# =============================

def generate_question(
    role: str,
    level: str,
    interview_type: str,
    language: str,
    question_no: int,
    previous_questions: List[str],
) -> str:
    previous_text = ""

    if previous_questions:
        previous_text = "\nAlready asked questions:\n"
        for q in previous_questions:
            previous_text += f"- {q}\n"

    prompt = f"""
You are an expert AI Interviewer.

Generate only ONE interview question.

Role: {role}
Level: {level}
Interview Type: {interview_type}
Language: {language}
Question Number: {question_no}

Rules:
- Ask only one question.
- Do not give the answer.
- Do not explain.
- Avoid repeated questions.
- Match the role and level.
- Output language must be {language}.
- Return valid JSON only.

{previous_text}

JSON format:
{{
  "question": "question here"
}}
"""

    result = ask_ai(prompt, json_mode=True)
    data = extract_json(result)

    if data and clean_text(data.get("question")):
        return clean_text(data["question"])

    return clean_text(result) or "Tell me about yourself and your relevant experience."


def evaluate_answer(
    role: str,
    level: str,
    interview_type: str,
    language: str,
    question: str,
    answer: str,
) -> Dict[str, Any]:
    if not clean_text(answer) or answer.startswith("TRANSCRIPTION_ERROR"):
        return {
            "score": 0,
            "feedback": "Audio is not clear.",
            "correct_answer": "Please answer clearly and close to microphone.",
            "is_follow_up_needed": True,
            "follow_up_question": "Can you answer the same question again clearly?",
        }

    prompt = f"""
You are an expert AI Interview Evaluator.

Evaluate the candidate answer.

Role: {role}
Level: {level}
Interview Type: {interview_type}
Language: {language}

Question:
{question}

Candidate Answer:
{answer}

Rules:
- Score out of 10.
- Feedback must be in {language}.
- Better correct answer must be in {language}.
- If answer is wrong, score low.
- If answer is irrelevant, score low.
- Keep feedback short and helpful.
- Return valid JSON only.

JSON format:
{{
  "score": 0,
  "feedback": "feedback here",
  "correct_answer": "better answer here",
  "is_follow_up_needed": true,
  "follow_up_question": "follow up question here or empty string"
}}
"""

    result = ask_ai(prompt, json_mode=True)
    data = extract_json(result)

    if not data:
        return {
            "score": 0,
            "feedback": "AI response JSON parse korte problem hoyeche.",
            "correct_answer": result,
            "is_follow_up_needed": False,
            "follow_up_question": "",
        }

    score = parse_score(data.get("score", 0))
    feedback = clean_text(data.get("feedback"))
    correct_answer = clean_text(data.get("correct_answer"))
    is_follow_up_needed = parse_bool(data.get("is_follow_up_needed", False))
    follow_up_question = clean_text(data.get("follow_up_question"))

    if not follow_up_question:
        is_follow_up_needed = False

    return {
        "score": score,
        "feedback": feedback,
        "correct_answer": correct_answer,
        "is_follow_up_needed": is_follow_up_needed,
        "follow_up_question": follow_up_question,
    }


def generate_final_report(
    user_name: str,
    role: str,
    level: str,
    interview_type: str,
    language: str,
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total_score = sum(parse_score(item.get("score", 0)) for item in history)
    max_score = len(history) * 10
    percentage = round((total_score / max_score) * 100, 2) if max_score > 0 else 0

    history_text = ""

    for item in history:
        history_text += f"""
Question {item["question_no"]}:
{item["question"]}

Voice Answer Text:
{item["answer"]}

Score:
{item["score"]}/10

Feedback:
{item["feedback"]}
"""

    prompt = f"""
You are an expert interview report generator.

Generate final interview report.

Candidate Name: {user_name}
Role: {role}
Level: {level}
Interview Type: {interview_type}
Language: {language}

Total Score: {total_score}/{max_score}
Percentage: {percentage}%

Interview History:
{history_text}

Rules:
- Report language must be {language}.
- Return valid JSON only.

JSON format:
{{
  "final_score": "{total_score}/{max_score}",
  "percentage": "{percentage}%",
  "overall_feedback": "overall feedback",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "improvement_plan": ["step 1", "step 2", "step 3"],
  "recommendation": "Selected / Need Improvement / Not Ready"
}}
"""

    result = ask_ai(prompt, json_mode=True)
    data = extract_json(result)

    if data:
        return {
            "final_score": clean_text(data.get("final_score", f"{total_score}/{max_score}")),
            "percentage": clean_text(data.get("percentage", f"{percentage}%")),
            "overall_feedback": clean_text(data.get("overall_feedback")),
            "strengths": data.get("strengths", []),
            "weaknesses": data.get("weaknesses", []),
            "improvement_plan": data.get("improvement_plan", []),
            "recommendation": clean_text(data.get("recommendation", "Need Improvement")),
        }

    return {
        "final_score": f"{total_score}/{max_score}",
        "percentage": f"{percentage}%",
        "overall_feedback": result,
        "strengths": [],
        "weaknesses": [],
        "improvement_plan": [],
        "recommendation": "Need Improvement",
    }


def save_report_to_file(
    user_name: str,
    role: str,
    level: str,
    interview_type: str,
    language: str,
    history: List[Dict[str, Any]],
    report: Dict[str, Any],
) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_name).strip("_") or "candidate"
    file_name = f"audio_interview_report_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(file_name, "w", encoding="utf-8") as file:
        file.write("AI Audio Interview Report\n")
        file.write("=========================\n\n")
        file.write(f"Candidate: {user_name}\n")
        file.write(f"Role: {role}\n")
        file.write(f"Level: {level}\n")
        file.write(f"Interview Type: {interview_type}\n")
        file.write(f"Language: {language}\n")
        file.write(f"LLM Model: {LLM_MODEL_NAME}\n")
        file.write(f"STT Model: {STT_MODEL_NAME}\n")
        file.write(f"AI Meet Account: {AI_AGENT_EMAIL}\n\n")

        file.write("Question Answer History\n")
        file.write("-----------------------\n\n")

        for item in history:
            file.write(f"Question {item['question_no']}: {item['question']}\n")
            file.write(f"Voice Answer Text: {item['answer']}\n")
            file.write(f"Score: {item['score']}/10\n")
            file.write(f"Feedback: {item['feedback']}\n")
            file.write(f"Better Answer: {item['correct_answer']}\n\n")

        file.write("Final Report\n")
        file.write("------------\n\n")
        file.write(json.dumps(report, ensure_ascii=False, indent=2))

    return os.path.abspath(file_name)


def print_list(title: str, items: Any) -> None:
    print(f"\n{title}:")

    if not items:
        print("- N/A")
        return

    if isinstance(items, list):
        for item in items:
            print(f"- {item}")
    else:
        print(f"- {items}")


# =============================
# MAIN
# =============================

def run_audio_interview() -> None:
    print("\n================================")
    print(" AI Google Meet Audio Interview Agent")
    print("================================")
    print(f"AI Meet Account: {AI_AGENT_EMAIL}")
    print(f"LLM Model: {LLM_MODEL_NAME}")
    print(f"Speech Model: {STT_MODEL_NAME}")

    check_audio_setup()

    print("\nBefore run:")
    print("1. Windows Playback default = CABLE Input")
    print(f"2. Google Meet Microphone  = {MEET_MIC_DEVICE_NAME}")
    print(f"3. Google Meet Speaker     = {MEET_SPEAKER_DEVICE_NAME}")
    print("4. Google Meet mic unmute")

    meet_link = input("\nGoogle Meet link/code dao. Skip korte ENTER: ").strip()

    if meet_link:
        open_google_meet(meet_link)

    speak("Voice test. I am your AI interview agent. I will ask you questions now.", "English")

    print("\nIMPORTANT TEST:")
    print("Ekhon candidate/another device theke AI voice shona jawar kotha.")
    print("Na shunle Windows Playback default CABLE Input ache kina abar check koro.")
    input("Voice test check kore ENTER dao... ")

    if not ollama_is_running():
        print("❌ Ollama running na.")
        print("CMD te run koro: ollama serve")
        return

    if not model_is_installed(LLM_MODEL_NAME):
        print(f"❌ Model installed na: {LLM_MODEL_NAME}")
        print(f"CMD te run koro: ollama pull {LLM_MODEL_NAME}")
        return

    if stt_model is None:
        print("❌ Speech recognition model load hoy nai.")
        return

    user_name = input("Candidate name: ").strip() or "Candidate"
    role = input("Role, example Flutter Developer: ").strip() or "Flutter Developer"
    level = input("Level, example Junior/Mid/Senior: ").strip() or "Mid"
    interview_type = input("Interview type, example Technical/HR/Mixed: ").strip() or "Technical"
    language = input("Language, example English/Bangla: ").strip() or "English"

    total_questions_input = input("Total questions, example 5: ").strip()

    try:
        total_questions = int(total_questions_input)
    except Exception:
        total_questions = 5

    if total_questions <= 0:
        total_questions = 5

    history: List[Dict[str, Any]] = []
    previous_questions: List[str] = []

    speak(
        "Interview room is ready. After every question, please answer after the beep. "
        "If you want to skip a question, say skip or next question.",
        language,
    )

    wait_for_candidate_start(language)

    current_question = generate_question(
        role=role,
        level=level,
        interview_type=interview_type,
        language=language,
        question_no=1,
        previous_questions=previous_questions,
    )

    try:
        for question_no in range(1, total_questions + 1):
            print("\n--------------------------------")
            print(f"Question {question_no}:")
            print(current_question)
            print("--------------------------------")

            speak(current_question, language)

            answer = listen_answer_auto(language, seconds=AUDIO_SECONDS)

            if is_skip_command(answer):
                evaluation = {
                    "score": 0,
                    "feedback": "Question skipped by candidate.",
                    "correct_answer": "Candidate skipped this question.",
                    "is_follow_up_needed": False,
                    "follow_up_question": "",
                }

                speak("Okay, moving to the next question.", language)

            else:
                evaluation = evaluate_answer(
                    role=role,
                    level=level,
                    interview_type=interview_type,
                    language=language,
                    question=current_question,
                    answer=answer,
                )

                print("\nResult:")
                print(f"Score: {evaluation['score']}/10")
                print(f"Feedback: {evaluation['feedback']}")
                print(f"Better Answer: {evaluation['correct_answer']}")

                speak(f"Your score is {evaluation['score']} out of 10.", "English")
                speak(evaluation["feedback"], language)

            history.append({
                "question_no": question_no,
                "question": current_question,
                "answer": answer,
                "score": evaluation["score"],
                "feedback": evaluation["feedback"],
                "correct_answer": evaluation["correct_answer"],
            })

            previous_questions.append(current_question)

            if question_no == total_questions:
                break

            if evaluation["is_follow_up_needed"] and evaluation["follow_up_question"]:
                current_question = evaluation["follow_up_question"]
            else:
                current_question = generate_question(
                    role=role,
                    level=level,
                    interview_type=interview_type,
                    language=language,
                    question_no=question_no + 1,
                    previous_questions=previous_questions,
                )

    except KeyboardInterrupt:
        print("\nInterview stopped by user.")

    if not history:
        print("\nNo interview data found.")
        return

    speak("Interview completed. I am generating your final report.", language)

    report = generate_final_report(
        user_name=user_name,
        role=role,
        level=level,
        interview_type=interview_type,
        language=language,
        history=history,
    )

    print("\n==============================")
    print(" Final Audio Interview Report")
    print("==============================")
    print(f"Final Score: {report.get('final_score')}")
    print(f"Percentage: {report.get('percentage')}")
    print(f"Recommendation: {report.get('recommendation')}")

    print("\nOverall Feedback:")
    print(report.get("overall_feedback"))

    print_list("Strengths", report.get("strengths", []))
    print_list("Weaknesses", report.get("weaknesses", []))
    print_list("Improvement Plan", report.get("improvement_plan", []))

    speak(f"Your final score is {report.get('final_score')}.", "English")
    speak(f"Recommendation is {report.get('recommendation')}.", language)

    file_name = save_report_to_file(
        user_name=user_name,
        role=role,
        level=level,
        interview_type=interview_type,
        language=language,
        history=history,
        report=report,
    )

    print(f"\n✅ Report saved: {file_name}")

    close_choice = input("\nGoogle Meet browser close korba? y/n: ").strip().lower()
    if close_choice == "y":
        close_google_meet()


if __name__ == "__main__":
    run_audio_interview()