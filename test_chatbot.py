"""Offline tests for matching, context, data errors, and the console loop."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import chatbot as app


class ChatbotTests(unittest.TestCase):
    def setUp(self):
        self.data = app.load_faq()
        self.bot = app.FAQBot(self.data)
        self.answers = [faq["answer"] for faq in self.data["faqs"]]

    def temporary_folder(self):
        temporary = tempfile.TemporaryDirectory(prefix="chatbot_test_", dir=app.PROJECT_DIR)
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def test_supplied_questions_return_unchanged_answers(self):
        self.assertEqual(len(self.data["faqs"]), 3)
        for faq in self.data["faqs"]:
            with self.subTest(question=faq["question"]):
                self.assertEqual(self.bot.reply(faq["question"]), [faq["answer"]])

    def test_case_punctuation_and_topic_variations(self):
        cases = {
            "  WHAT ARE YOUR HOURS?!  ": self.answers[0],
            "When do you open?": self.answers[0],
            "Where can I upload my project?": self.answers[1],
            "When will I get my certificate?": self.answers[2],
        }
        for message, answer in cases.items():
            with self.subTest(message=message):
                self.assertEqual(self.bot.reply(message), [answer])

    def test_greetings_do_not_match_inside_words(self):
        self.assertEqual(self.bot.reply("HI!!!"), ["Hello! How can I help?"])
        response = self.bot.reply("Explain this thing to me")
        self.assertFalse(any(message.startswith("Hello!") for message in response))
        self.assertIn("FAQ", response[0])

    def test_multiple_intents_are_answered_once_in_dataset_order(self):
        response = self.bot.reply(
            "Hi! Tell me your hours and opening hours, how to submit my project, and about certificates."
        )
        self.assertEqual(response[0], "Hello! How can I help?")
        self.assertEqual(response[1:], self.answers)
        self.assertEqual(self.bot.state, "resolution")

    def test_help_number_selection_and_invalid_numbers(self):
        menu = self.bot.reply("help")[0]
        self.assertIn("1. " + self.data["faqs"][0]["question"], menu)
        self.assertEqual(self.bot.reply("3"), [self.answers[2]])
        for number in ("0", "4", "9" * 5000):
            with self.subTest(length=len(number)):
                self.assertIn("from 1 to 3", self.bot.reply(number)[0])
                self.assertEqual(self.bot.last_matches, [])

    def test_certificate_duration_followup_uses_correct_context(self):
        self.bot.reply("certificate")
        self.assertEqual(self.bot.reply("How long does that take?"), [self.answers[2]])
        self.bot.reply("hours")
        self.assertIn("Which topic", self.bot.reply("how long?")[0])

    def test_ambiguous_followups_request_clarification(self):
        self.assertIn("Which topic", self.bot.reply("how long?")[0])
        self.bot.reply("hours and certificates")
        response = self.bot.reply("how long does that take?")
        self.assertIn("Which topic", response[0])
        self.assertIn("Available questions", response[1])

    def test_submission_followup_and_repeat(self):
        self.bot.reply("How do I submit my project?")
        self.assertEqual(self.bot.reply("Where do I send it?"), [self.answers[1]])
        self.assertEqual(self.bot.reply("repeat"), [self.answers[1]])
        self.bot.reply("hours and certificates")
        self.assertEqual(self.bot.reply("again"), [self.answers[0], self.answers[2]])

    def test_unknown_question_clears_context_and_offers_help(self):
        self.bot.reply("certificate")
        response = self.bot.reply("What is the weather?")
        self.assertIn("don't have an answer", response[0])
        self.assertEqual(self.bot.last_matches, [])
        self.assertIn("Which topic", self.bot.reply("how long?")[0])
        self.bot.reply("unknown topic")
        self.assertTrue(any("Available questions" in text for text in self.bot.reply("another mystery")))
        self.assertEqual(self.bot.reply(" !!! "), ["Please type a question, 'help', or 'bye'."])

    def test_whole_message_exits_and_exit_substring_safety(self):
        for command in ("bye", "EXIT!!!", " Quit "):
            with self.subTest(command=command):
                bot = app.FAQBot(self.data)
                self.assertIn("Goodbye", bot.reply(command)[0])
                self.assertEqual(bot.state, "exit")
        self.bot.reply("How do I quit my internship?")
        self.assertNotEqual(self.bot.state, "exit")

    def test_additional_faq_supports_exact_and_word_matching(self):
        data = {"greetings": ["hi"], "faqs": [{
            "question": "How do I reset my password?", "answer": "Use the password reset form."
        }]}
        bot = app.FAQBot(data)
        self.assertEqual(bot.reply("How do I reset my password?"), [data["faqs"][0]["answer"]])
        self.assertEqual(bot.reply("reset account password"), [data["faqs"][0]["answer"]])

    def test_invalid_and_missing_json_have_clear_errors(self):
        path = self.temporary_folder() / "faq.json"
        with self.assertRaises(OSError):
            app.load_faq(path)
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            app.load_faq(path)
        invalid_data = [
            [], {}, {"greetings": "hi", "faqs": []},
            {"greetings": ["hi"], "faqs": ["wrong type"]},
            {"greetings": ["hi"], "faqs": [{"question": "Hours?", "answer": ""}]},
            {"greetings": ["hi"], "faqs": [
                {"question": "Hours?", "answer": "One"},
                {"question": "HOURS!", "answer": "Two"},
            ]},
        ]
        for data in invalid_data:
            with self.subTest(data=data):
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(app.FAQDataError):
                    app.load_faq(path)

    def test_console_loop_and_keyboard_exits(self):
        output = io.StringIO()
        with patch("builtins.input", side_effect=["hi", "hours and certificates", "bye"]):
            with contextlib.redirect_stdout(output):
                self.assertEqual(app.main([]), 0)
        self.assertIn(self.answers[0], output.getvalue())
        self.assertIn(self.answers[2], output.getvalue())
        self.assertIn("Goodbye", output.getvalue())
        for interruption in (EOFError, KeyboardInterrupt):
            with self.subTest(interruption=interruption.__name__):
                with patch("builtins.input", side_effect=interruption):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(app.main([]), 0)

    def test_script_finds_adjacent_json_from_another_working_directory(self):
        result = subprocess.run(
            [sys.executable, str(app.PROJECT_DIR / "chatbot.py")],
            input="bye\n", text=True, capture_output=True,
            cwd=self.temporary_folder(), timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 questions", result.stdout)
        self.assertIn("Goodbye", result.stdout)


if __name__ == "__main__":
    unittest.main()
