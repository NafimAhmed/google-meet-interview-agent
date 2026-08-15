"""Human-readable interview report output."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from interview_agent.config import Settings
from interview_agent.models import History, InterviewProfile, Report


def save_report(
    profile: InterviewProfile,
    history: History,
    report: Report,
    config: Settings,
) -> Path:
    safe_name = (
        re.sub(r"[^a-zA-Z0-9_-]+", "_", profile.candidate_name).strip("_")
        or "candidate"
    )
    file_name = (
        f"audio_interview_report_{safe_name}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    output_path = Path(file_name).resolve()

    with output_path.open("w", encoding="utf-8") as file:
        file.write("AI Audio Interview Report\n")
        file.write("=========================\n\n")
        file.write(f"Candidate: {profile.candidate_name}\n")
        file.write(f"Role: {profile.role}\n")
        file.write(f"Level: {profile.level}\n")
        file.write(f"Interview Type: {profile.interview_type}\n")
        file.write(f"Language: {profile.language}\n")
        file.write(f"LLM Model: {config.llm_model_name}\n")
        file.write(f"STT Model: {config.stt_model_name}\n")
        file.write(f"AI Meet Account: {config.ai_agent_email}\n\n")
        file.write("Question Answer History\n")
        file.write("-----------------------\n\n")

        for item in history:
            file.write(
                f"Question {item['question_no']}: {item['question']}\n"
            )
            file.write(f"Voice Answer Text: {item['answer']}\n")
            file.write(f"Score: {item['score']}/10\n")
            file.write(f"Feedback: {item['feedback']}\n")
            file.write(f"Better Answer: {item['correct_answer']}\n\n")

        file.write("Final Report\n")
        file.write("------------\n\n")
        file.write(json.dumps(report, ensure_ascii=False, indent=2))

    return output_path


def print_list(title: str, items: Any) -> None:
    print(f"\n{title}:")
    if not items:
        print("- N/A")
    elif isinstance(items, list):
        for item in items:
            print(f"- {item}")
    else:
        print(f"- {items}")
