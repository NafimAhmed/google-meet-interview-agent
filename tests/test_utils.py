import unittest

from interview_agent.utils import (
    extract_json,
    has_bangla,
    is_skip_command,
    is_start_command,
    parse_bool,
    parse_score,
)


class UtilsTests(unittest.TestCase):
    def test_extract_json_from_markdown_fence(self) -> None:
        self.assertEqual(
            extract_json('```json\n{"score": 8}\n```'), {"score": 8}
        )

    def test_extract_json_from_surrounding_text(self) -> None:
        self.assertEqual(
            extract_json('Result: {"question": "Why?"} done'),
            {"question": "Why?"},
        )

    def test_score_is_clamped(self) -> None:
        self.assertEqual(parse_score("12/10"), 10)
        self.assertEqual(parse_score(-4), 0)
        self.assertEqual(parse_score("score 7"), 7)

    def test_boolean_parsing(self) -> None:
        self.assertTrue(parse_bool("yes"))
        self.assertTrue(parse_bool(1))
        self.assertFalse(parse_bool("no"))

    def test_bangla_detection(self) -> None:
        self.assertTrue(has_bangla("আমি প্রস্তুত"))
        self.assertFalse(has_bangla("I am ready"))

    def test_start_command_uses_word_boundaries(self) -> None:
        self.assertTrue(is_start_command("Okay, I am ready"))
        self.assertTrue(is_start_command("আমি প্রস্তুত"))
        self.assertFalse(is_start_command("yesterday"))

    def test_skip_command(self) -> None:
        self.assertTrue(is_skip_command("Next question please"))
        self.assertTrue(is_skip_command("আমি জানি না"))
        self.assertFalse(is_skip_command("I know the answer"))


if __name__ == "__main__":
    unittest.main()
