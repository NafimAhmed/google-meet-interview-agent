"""Ollama HTTP client."""

from typing import Any, Dict, List

import requests

from interview_agent.config import Settings
from interview_agent.utils import clean_text


class OllamaClient:
    def __init__(self, config: Settings) -> None:
        self.config = config

    def is_running(self) -> bool:
        try:
            response = requests.get(
                f"{self.config.ollama_base_url}/api/tags", timeout=10
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def installed_models(self) -> List[str]:
        try:
            response = requests.get(
                f"{self.config.ollama_base_url}/api/tags", timeout=10
            )
            if response.status_code != 200:
                return []
            models = response.json().get("models", [])
            return [
                item.get("name", "")
                for item in models
                if item.get("name")
            ]
        except (requests.RequestException, ValueError, AttributeError):
            return []

    def model_is_installed(self) -> bool:
        return self.config.llm_model_name in self.installed_models()

    def generate(self, prompt: str, json_mode: bool = False) -> str:
        payload: Dict[str, Any] = {
            "model": self.config.llm_model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "top_p": 0.9},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = requests.post(
                self.config.ollama_generate_url,
                json=payload,
                timeout=self.config.request_timeout,
            )
            if response.status_code != 200:
                return f"OLLAMA_ERROR: {response.text}"
            return clean_text(response.json().get("response", ""))
        except requests.ConnectionError:
            return "OLLAMA_CONNECTION_ERROR: Ollama server running na."
        except requests.Timeout:
            return "OLLAMA_TIMEOUT_ERROR: Model response dite beshi time nicche."
        except Exception as error:
            return f"PYTHON_ERROR: {error}"
