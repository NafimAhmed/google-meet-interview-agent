"""Google Meet browser automation."""

import re
import time
from typing import Any, Optional

from interview_agent.config import Settings
from interview_agent.utils import clean_text

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - dependency is optional until Meet is used
    sync_playwright = None


def normalize_meet_url(value: str) -> str:
    normalized = clean_text(value)
    if not normalized:
        return ""
    if normalized.startswith(("http://", "https://")):
        return normalized
    code = normalized.replace("meet.google.com/", "").strip("/")
    return f"https://meet.google.com/{code}"


class GoogleMeetSession:
    """Owns the Playwright lifecycle for one Google Meet session."""

    def __init__(self, config: Settings) -> None:
        self.config = config
        self._playwright: Optional[Any] = None
        self._context: Optional[Any] = None
        self._page: Optional[Any] = None

    @staticmethod
    def _safe_click(page: Any, pattern: str, timeout: int = 5000) -> bool:
        try:
            page.get_by_role(
                "button", name=re.compile(pattern, re.IGNORECASE)
            ).click(timeout=timeout)
            return True
        except Exception:
            return False

    def open(self, meet_url: str) -> bool:
        normalized_url = normalize_meet_url(meet_url)
        if not normalized_url:
            print("Google Meet link empty.")
            return False
        if sync_playwright is None:
            print("\n❌ Playwright installed na.")
            print("CMD te run koro:")
            print("py -m pip install playwright")
            print("py -m playwright install chromium")
            return False

        print("\n==============================")
        print("Opening Google Meet")
        print("==============================")
        print(f"AI account: {self.config.ai_agent_email}")
        print(f"Meet URL: {normalized_url}")
        print(f"Chrome profile: {self.config.chrome_profile_dir}")

        try:
            self._playwright = sync_playwright().start()
            launch_args = [
                "--use-fake-ui-for-media-stream",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ]
            launch_options = {
                "user_data_dir": str(self.config.chrome_profile_dir),
                "headless": False,
                "args": launch_args,
                "viewport": None,
            }
            try:
                self._context = (
                    self._playwright.chromium.launch_persistent_context(
                        channel="chrome", **launch_options
                    )
                )
            except Exception:
                self._context = (
                    self._playwright.chromium.launch_persistent_context(
                        **launch_options
                    )
                )

            try:
                self._context.grant_permissions(
                    ["microphone", "camera"],
                    origin="https://meet.google.com",
                )
            except Exception:
                pass

            self._page = self._context.new_page()
            self._page.goto(
                normalized_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            time.sleep(5)
            self._safe_click(
                self._page, r"Got it|Dismiss|Close|Allow", timeout=3000
            )
            self._safe_click(self._page, r"Turn off camera", timeout=3000)

            joined = any(
                self._safe_click(self._page, pattern, timeout=8000)
                for pattern in (
                    r"Join now",
                    r"Ask to join",
                    r"Request to join",
                    r"Join",
                )
            )
            if joined:
                print("✅ Join button clicked.")
                print("Host accept lagle host-ke accept korte hobe.")
            else:
                print(
                    "⚠️ Auto join click hoy nai. Browser e manually "
                    "Join / Ask to join click koro."
                )

            print("\nMeet Settings > Audio e eta set koro:")
            print(f"Microphone = {self.config.meet_mic_device_name}")
            print(f"Speaker    = {self.config.meet_speaker_device_name}")
            print("Mic unmute rakhba.")
            input("\nMeet setup complete hole ENTER press koro... ")
            return True
        except Exception as error:
            print(f"❌ Google Meet open error: {error}")
            self.close()
            return False

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._playwright = None
        self._context = None
        self._page = None
