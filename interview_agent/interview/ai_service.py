"""LLM-powered interview operations."""

from typing import Any, Dict, List

from interview_agent.integrations.ollama import OllamaClient
from interview_agent.models import Evaluation, History, InterviewProfile, Report
from interview_agent.utils import clean_text, extract_json, parse_bool, parse_score


class InterviewAI:
    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def generate_question(
        self,
        profile: InterviewProfile,
        question_no: int,
        previous_questions: List[str],
    ) -> str:
        previous_text = ""
        if previous_questions:
            previous_text = "\nAlready asked questions:\n" + "".join(
                f"- {question}\n" for question in previous_questions
            )

        prompt = f"""
You are an expert AI Interviewer.

Generate only ONE interview question.

Role: {profile.role}
Level: {profile.level}
Interview Type: {profile.interview_type}
Language: {profile.language}
Question Number: {question_no}

Rules:
- Ask only one question.
- Do not give the answer.
- Do not explain.
- Avoid repeated questions.
- Match the role and level.
- Output language must be {profile.language}.
- Return valid JSON only.

{previous_text}

JSON format:
{{
  "question": "question here"
}}
"""
        result = self.client.generate(prompt, json_mode=True)
        data = extract_json(result)
        if data and clean_text(data.get("question")):
            return clean_text(data["question"])
        return clean_text(result) or (
            "Tell me about yourself and your relevant experience."
        )

    def evaluate_answer(
        self,
        profile: InterviewProfile,
        question: str,
        answer: str,
    ) -> Evaluation:
        if not clean_text(answer) or answer.startswith("TRANSCRIPTION_ERROR"):
            return {
                "score": 0,
                "feedback": "Audio is not clear.",
                "correct_answer": (
                    "Please answer clearly and close to microphone."
                ),
                "is_follow_up_needed": True,
                "follow_up_question": (
                    "Can you answer the same question again clearly?"
                ),
            }

        prompt = f"""
You are an expert AI Interview Evaluator.

Evaluate the candidate answer.

Role: {profile.role}
Level: {profile.level}
Interview Type: {profile.interview_type}
Language: {profile.language}

Question:
{question}

Candidate Answer:
{answer}

Rules:
- Score out of 10.
- Feedback must be in {profile.language}.
- Better correct answer must be in {profile.language}.
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
        result = self.client.generate(prompt, json_mode=True)
        data = extract_json(result)
        if not data:
            return {
                "score": 0,
                "feedback": "AI response JSON parse korte problem hoyeche.",
                "correct_answer": result,
                "is_follow_up_needed": False,
                "follow_up_question": "",
            }

        follow_up_question = clean_text(data.get("follow_up_question"))
        return {
            "score": parse_score(data.get("score", 0)),
            "feedback": clean_text(data.get("feedback")),
            "correct_answer": clean_text(data.get("correct_answer")),
            "is_follow_up_needed": bool(follow_up_question)
            and parse_bool(data.get("is_follow_up_needed", False)),
            "follow_up_question": follow_up_question,
        }

    def generate_final_report(
        self, profile: InterviewProfile, history: History
    ) -> Report:
        total_score = sum(parse_score(item.get("score", 0)) for item in history)
        max_score = len(history) * 10
        percentage = (
            round((total_score / max_score) * 100, 2) if max_score else 0
        )
        history_text = "".join(
            f"""
Question {item['question_no']}:
{item['question']}

Voice Answer Text:
{item['answer']}

Score:
{item['score']}/10

Feedback:
{item['feedback']}
"""
            for item in history
        )

        prompt = f"""
You are an expert interview report generator.

Generate final interview report.

Candidate Name: {profile.candidate_name}
Role: {profile.role}
Level: {profile.level}
Interview Type: {profile.interview_type}
Language: {profile.language}

Total Score: {total_score}/{max_score}
Percentage: {percentage}%

Interview History:
{history_text}

Rules:
- Report language must be {profile.language}.
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
        result = self.client.generate(prompt, json_mode=True)
        data: Dict[str, Any] = extract_json(result) or {}
        if data:
            return {
                "final_score": clean_text(
                    data.get("final_score", f"{total_score}/{max_score}")
                ),
                "percentage": clean_text(
                    data.get("percentage", f"{percentage}%")
                ),
                "overall_feedback": clean_text(data.get("overall_feedback")),
                "strengths": data.get("strengths", []),
                "weaknesses": data.get("weaknesses", []),
                "improvement_plan": data.get("improvement_plan", []),
                "recommendation": clean_text(
                    data.get("recommendation", "Need Improvement")
                ),
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
