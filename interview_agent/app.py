"""Application orchestration for the command-line interview flow."""

import sys
from typing import List

from interview_agent.audio.devices import check_audio_setup
from interview_agent.audio.recorder import AudioRecorder
from interview_agent.audio.tts import TextToSpeech
from interview_agent.config import Settings, settings
from interview_agent.integrations.google_meet import GoogleMeetSession
from interview_agent.integrations.ollama import OllamaClient
from interview_agent.interview.ai_service import InterviewAI
from interview_agent.models import Evaluation, History, InterviewProfile
from interview_agent.reporting import print_list, save_report
from interview_agent.speech.recognizer import SpeechRecognizer
from interview_agent.utils import is_skip_command, is_start_command


def _configure_unicode_console() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def _read_total_questions() -> int:
    try:
        value = int(input("Total questions, example 5: ").strip())
        return value if value > 0 else 5
    except ValueError:
        return 5


def _read_profile() -> InterviewProfile:
    return InterviewProfile(
        candidate_name=input("Candidate name: ").strip() or "Candidate",
        role=input("Role, example Flutter Developer: ").strip()
        or "Flutter Developer",
        level=input("Level, example Junior/Mid/Senior: ").strip() or "Mid",
        interview_type=input(
            "Interview type, example Technical/HR/Mixed: "
        ).strip()
        or "Technical",
        language=input("Language, example English/Bangla: ").strip()
        or "English",
        total_questions=_read_total_questions(),
    )


def _wait_for_candidate_start(
    profile: InterviewProfile,
    recognizer: SpeechRecognizer,
    tts: TextToSpeech,
    config: Settings,
) -> None:
    tts.speak(
        "Interview is ready. Please say yes or ok to start.",
        profile.language,
    )
    for attempt in range(1, 4):
        print(f"\nStart confirmation attempt {attempt}/3")
        answer = recognizer.listen(
            profile.language, config.confirmation_audio_seconds
        )
        if is_start_command(answer):
            tts.speak("Great. Interview started.", profile.language)
            return
        tts.speak(
            "I could not understand. Please say yes or ok to start.",
            profile.language,
        )

    print("⚠️ Start confirmation clear na. Interview auto start hocche.")
    tts.speak("I will start the interview now.", profile.language)


def _run_questions(
    profile: InterviewProfile,
    interview_ai: InterviewAI,
    recognizer: SpeechRecognizer,
    tts: TextToSpeech,
    config: Settings,
) -> History:
    history: History = []
    previous_questions: List[str] = []
    current_question = interview_ai.generate_question(
        profile, question_no=1, previous_questions=previous_questions
    )

    try:
        for question_no in range(1, profile.total_questions + 1):
            print("\n--------------------------------")
            print(f"Question {question_no}:")
            print(current_question)
            print("--------------------------------")
            tts.speak(current_question, profile.language)

            answer = recognizer.listen(profile.language, config.audio_seconds)
            if is_skip_command(answer):
                evaluation: Evaluation = {
                    "score": 0,
                    "feedback": "Question skipped by candidate.",
                    "correct_answer": "Candidate skipped this question.",
                    "is_follow_up_needed": False,
                    "follow_up_question": "",
                }
                tts.speak(
                    "Okay, moving to the next question.", profile.language
                )
            else:
                evaluation = interview_ai.evaluate_answer(
                    profile, current_question, answer
                )
                print("\nResult:")
                print(f"Score: {evaluation['score']}/10")
                print(f"Feedback: {evaluation['feedback']}")
                print(f"Better Answer: {evaluation['correct_answer']}")
                tts.speak(
                    f"Your score is {evaluation['score']} out of 10.",
                    "English",
                )
                tts.speak(evaluation["feedback"], profile.language)

            history.append(
                {
                    "question_no": question_no,
                    "question": current_question,
                    "answer": answer,
                    "score": evaluation["score"],
                    "feedback": evaluation["feedback"],
                    "correct_answer": evaluation["correct_answer"],
                }
            )
            previous_questions.append(current_question)

            if question_no == profile.total_questions:
                break
            if (
                evaluation["is_follow_up_needed"]
                and evaluation["follow_up_question"]
            ):
                current_question = evaluation["follow_up_question"]
            else:
                current_question = interview_ai.generate_question(
                    profile,
                    question_no=question_no + 1,
                    previous_questions=previous_questions,
                )
    except KeyboardInterrupt:
        print("\nInterview stopped by user.")

    return history


def run_audio_interview(config: Settings = settings) -> None:
    _configure_unicode_console()
    meet = GoogleMeetSession(config)
    tts = TextToSpeech(config)
    ollama = OllamaClient(config)
    recorder = AudioRecorder(config)
    recognizer = SpeechRecognizer(config, recorder)
    interview_ai = InterviewAI(ollama)

    print("\n================================")
    print(" AI Google Meet Audio Interview Agent")
    print("================================")
    print(f"AI Meet Account: {config.ai_agent_email}")
    print(f"LLM Model: {config.llm_model_name}")
    print(f"Speech Model: {config.stt_model_name}")
    check_audio_setup(config)

    print("\nBefore run:")
    print("1. Windows Playback default = CABLE Input")
    print(f"2. Google Meet Microphone  = {config.meet_mic_device_name}")
    print(f"3. Google Meet Speaker     = {config.meet_speaker_device_name}")
    print("4. Google Meet mic unmute")

    meet_link = input("\nGoogle Meet link/code dao. Skip korte ENTER: ").strip()
    if meet_link:
        meet.open(meet_link)

    tts.speak(
        "Voice test. I am your AI interview agent. "
        "I will ask you questions now.",
        "English",
    )
    print("\nIMPORTANT TEST:")
    print("Ekhon candidate/another device theke AI voice shona jawar kotha.")
    print("Na shunle Windows Playback default CABLE Input ache kina abar check koro.")
    input("Voice test check kore ENTER dao... ")

    if not ollama.is_running():
        print("❌ Ollama running na.")
        print("CMD te run koro: ollama serve")
        return
    if not ollama.model_is_installed():
        print(f"❌ Model installed na: {config.llm_model_name}")
        print(f"CMD te run koro: ollama pull {config.llm_model_name}")
        return
    if not recognizer.load():
        return

    profile = _read_profile()
    tts.speak(
        "Interview room is ready. After every question, please answer "
        "after the beep. If you want to skip a question, say skip or "
        "next question.",
        profile.language,
    )
    _wait_for_candidate_start(profile, recognizer, tts, config)
    history = _run_questions(
        profile, interview_ai, recognizer, tts, config
    )
    if not history:
        print("\nNo interview data found.")
        return

    tts.speak(
        "Interview completed. I am generating your final report.",
        profile.language,
    )
    report = interview_ai.generate_final_report(profile, history)
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

    tts.speak(f"Your final score is {report.get('final_score')}.", "English")
    tts.speak(
        f"Recommendation is {report.get('recommendation')}.",
        profile.language,
    )
    report_path = save_report(profile, history, report, config)
    print(f"\n✅ Report saved: {report_path}")

    if input("\nGoogle Meet browser close korba? y/n: ").strip().lower() == "y":
        meet.close()
