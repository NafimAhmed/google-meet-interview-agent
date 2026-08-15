# Google Meet Interview Agent

Windows-based voice interview agent that joins Google Meet, asks AI-generated
questions through TTS, transcribes the candidate with Faster Whisper, evaluates
answers through a local Ollama model, and creates a final text report.

## Project structure

```text
.
├── main.py                         # Small CLI entry point
├── interview_agent/
│   ├── app.py                      # Interview workflow orchestration
│   ├── config.py                   # Central environment-based settings
│   ├── models.py                   # Domain types
│   ├── reporting.py                # Report output
│   ├── utils.py                    # Pure parsing helpers
│   ├── audio/
│   │   ├── devices.py              # Audio discovery and diagnostics
│   │   ├── recorder.py             # Candidate recording
│   │   └── tts.py                  # Edge TTS and SAPI fallback
│   ├── integrations/
│   │   ├── google_meet.py          # Playwright Meet session
│   │   └── ollama.py               # Ollama HTTP client
│   ├── interview/
│   │   └── ai_service.py           # Questions, evaluation, final report
│   └── speech/
│       └── recognizer.py            # Faster Whisper STT
└── tests/
    └── test_utils.py
```

## Prerequisites

- Windows 10/11 and Python 3.10+
- Google Chrome
- [Ollama](https://ollama.com/)
- VB-Audio Virtual Cable with the required 16-channel devices

The default audio routing remains:

- Windows Playback Default: `CABLE Input`
- Google Meet Microphone: `CABLE Output`
- Google Meet Speaker: `CABLE In 16ch`
- Python STT Input: `CABLE Out 16ch`

## Installation

Open PowerShell in the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m playwright install chromium
ollama pull qwen2.5:3b
```

Start Ollama if it is not already running:

```powershell
ollama serve
```

Run the agent:

```powershell
py main.py
```

## Configuration

Defaults are defined in `interview_agent/config.py`. Copy `.env.example` as a
reference and set any override in PowerShell before starting the app:

```powershell
$env:AI_AGENT_EMAIL = "your-agent@gmail.com"
$env:LLM_MODEL_NAME = "qwen2.5:3b"
py main.py
```

The application does not read `.env` automatically, so secrets are never loaded
from a committed file by accident.

## Tests

The pure helpers can be tested without audio, Ollama, or Google Meet:

```powershell
py -m unittest discover -s tests -v
```
