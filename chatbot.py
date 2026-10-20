"""An offline, rule-based FAQ chatbot. Run: python chatbot.py"""

import argparse
import json
from pathlib import Path
import re
import sys


PROJECT_DIR = Path(__file__).resolve().parent
FAQ_PATH = PROJECT_DIR / "sample_faq.json"
EXIT_COMMANDS = {"bye", "goodbye", "exit", "quit"}
HELP_COMMANDS = {"help", "menu", "faq", "faqs", "topics", "what can you do"}
REPEAT_COMMANDS = {"repeat", "again", "repeat that", "say that again", "tell me again"}
THANKS_COMMANDS = {"thanks", "thank you", "thanks for your help", "thank you for your help"}
DURATION_FOLLOWUPS = {
    "how long", "how many days", "how long does it take", "how long does that take",
    "how long will it take", "when will i get it", "when will i receive it",
}
SUBMISSION_FOLLOWUPS = {
    "where do i send it", "where do i submit it", "where should i upload it",
    "where do i upload it", "where should i send it",
}
STOP_WORDS = {
    "a", "an", "and", "are", "be", "can", "do", "does", "for", "from", "how",
    "i", "in", "is", "it", "me", "my", "of", "on", "please", "s", "that",
    "the", "their", "this", "to", "we", "what", "when", "where", "which", "will",
    "with", "you", "your",
}


class FAQDataError(ValueError):
    """The JSON was readable but did not have the expected FAQ structure."""


def normalize(text):
    """Lowercase and collapse punctuation/whitespace for consistent matching."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def content_words(text):
    return set(normalize(text).split()) - STOP_WORDS


def load_faq(path=FAQ_PATH):
    """Load and validate the provided greetings/FAQ JSON without modifying it."""
    with Path(path).open(encoding="utf-8-sig") as source:
        data = json.load(source)
    if not isinstance(data, dict):
        raise FAQDataError("The JSON must be an object containing greetings and faqs.")
    greetings = data.get("greetings")
    faqs = data.get("faqs")
    if (not isinstance(greetings, list) or not greetings
            or not all(isinstance(item, str) and normalize(item) for item in greetings)):
        raise FAQDataError("greetings must be a non-empty list of greeting strings.")
    if not isinstance(faqs, list) or not faqs:
        raise FAQDataError("faqs must be a non-empty list of question/answer objects.")
    seen = set()
    for number, faq in enumerate(faqs, start=1):
        if not isinstance(faq, dict):
            raise FAQDataError(f"FAQ {number} must be an object.")
        for field in ("question", "answer"):
            if not isinstance(faq.get(field), str) or not faq[field].strip():
                raise FAQDataError(f"FAQ {number} needs a non-empty {field} string.")
        question = normalize(faq["question"])
        if not question or question in seen:
            raise FAQDataError(f"FAQ {number} has an empty or duplicate normalized question.")
        seen.add(question)
    return data


class FAQBot:
    """Track conversation context and return one response per recognized intent."""

    def __init__(self, data):
        self.faqs = data["faqs"]
        phrases = sorted({normalize(item) for item in data["greetings"]}, key=len, reverse=True)
        self.greeting_pattern = re.compile(r"\b(?:" + "|".join(re.escape(item) for item in phrases) + r")\b")
        self.keywords = [content_words(faq["question"]) for faq in self.faqs]
        self.kinds = []
        for words in self.keywords:
            if "hours" in words or "operation" in words:
                self.kinds.append("hours")
            elif "submit" in words and words & {"project", "internship"}:
                self.kinds.append("submission")
            elif "certificate" in words or "certificates" in words:
                self.kinds.append("certificate")
            else:
                self.kinds.append("custom")
        self.last_matches = []
        self.unknown_count = 0
        self.state = "greeting"

    def welcome(self):
        self.state = "awaiting_query"
        return "Hello! I am the FAQ assistant. Type 'help' for questions or 'bye' to leave."

    def menu(self):
        questions = "\n".join(f"{index}. {faq['question']}" for index, faq in enumerate(self.faqs, 1))
        return f"Available questions:\n{questions}\nAsk a question or enter its number."

    def answer(self, indices):
        self.last_matches = list(dict.fromkeys(indices))
        self.unknown_count = 0
        self.state = "resolution"
        return [self.faqs[index]["answer"] for index in self.last_matches]

    def clarify(self):
        self.last_matches = []
        self.state = "clarification"
        return ["Which topic do you mean?", self.menu()]

    def match_intents(self, query):
        """Use exact questions, topic regexes, then conservative word overlap."""
        words = content_words(query)
        matches = []
        for index, faq in enumerate(self.faqs):
            kind = self.kinds[index]
            exact = query == normalize(faq["question"])
            if kind == "hours":
                topic_match = bool(re.search(
                    r"\b(?:hours?|opening|closing|operation|operating|weekends?)\b"
                    r"|\b(?:when|what time)\b.{0,35}\b(?:open|close)\b"
                    r"|\bare you (?:open|closed)\b", query
                ))
            elif kind == "submission":
                action = bool(re.search(r"\b(?:submit|submitting|submission|upload|uploading|hand in|turn in|send)\b", query))
                subject = bool(words & {"project", "internship", "github", "repository", "repo", "link", "code"})
                topic_match = (action and subject) or query in {
                    "submit", "submission", "project submission", "how do i submit",
                    "how can i submit", "how to submit", "student workspace",
                }
            elif kind == "certificate":
                topic_match = bool(re.search(r"\b(?:certificates?|certification)\b", query))
            else:
                overlap = words & self.keywords[index]
                topic_match = len(overlap) >= 2 and len(overlap) >= len(self.keywords[index]) / 2
            if exact or topic_match:
                matches.append(index)
        return matches

    def reply(self, message):
        if self.state == "exit":
            return ["This chat has ended. Restart the program to begin again."]
        query = normalize(message)
        if not query:
            return ["Please type a question, 'help', or 'bye'."]
        # Whole-message matching avoids exiting for a phrase like 'quit my internship'.
        if query in EXIT_COMMANDS:
            self.state = "exit"
            return ["Goodbye! Thanks for chatting."]
        if query in HELP_COMMANDS:
            self.last_matches = []
            self.unknown_count = 0
            self.state = "awaiting_query"
            return [self.menu()]
        if query in THANKS_COMMANDS:
            return ["You're welcome! Ask another question or type 'bye' to leave."]
        if query in REPEAT_COMMANDS:
            return self.answer(self.last_matches) if self.last_matches else self.clarify()
        if query in DURATION_FOLLOWUPS or query in SUBMISSION_FOLLOWUPS:
            expected_kind = "certificate" if query in DURATION_FOLLOWUPS else "submission"
            if len(self.last_matches) == 1 and self.kinds[self.last_matches[0]] == expected_kind:
                return self.answer(self.last_matches)
            return self.clarify()
        if query.isdigit():
            try:
                number = int(query)
            except ValueError:
                number = 0
            if 1 <= number <= len(self.faqs):
                return self.answer([number - 1])
            self.state = "clarification"
            self.last_matches = []
            return [f"Choose a question number from 1 to {len(self.faqs)}."]

        greeted = bool(self.greeting_pattern.search(query))
        prefix = ["Hello! How can I help?"] if greeted else []
        matches = self.match_intents(query)
        if matches:
            return prefix + self.answer(matches)
        remainder = self.greeting_pattern.sub(" ", query)
        if greeted and set(remainder.split()) <= {"there", "bot", "assistant", "everyone"}:
            self.last_matches = []
            self.unknown_count = 0
            self.state = "awaiting_query"
            return prefix

        # An unknown question clears old context rather than guessing a stale answer.
        self.last_matches = []
        self.unknown_count += 1
        self.state = "clarification"
        responses = prefix + ["I don't have an answer to that in the FAQ. Try rephrasing, or type 'help'."]
        if self.unknown_count >= 2:
            responses.append(self.menu())
        return responses


def print_responses(responses):
    for response in responses:
        lines = response.splitlines()
        print(f"Bot: {lines[0]}")
        for line in lines[1:]:
            print(f"     {line}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--faq", type=Path, default=FAQ_PATH, help="Path to a greetings/FAQ JSON file.")
    args = parser.parse_args(argv)
    try:
        data = load_faq(args.faq)
    except (OSError, UnicodeError, json.JSONDecodeError, FAQDataError) as error:
        print(f"Cannot load FAQ data: {error}", file=sys.stderr)
        print("Keep a valid sample_faq.json beside chatbot.py, or provide --faq PATH.", file=sys.stderr)
        return 1

    bot = FAQBot(data)
    print("=" * 45)
    print("          RULE-BASED FAQ CHATBOT")
    print("=" * 45)
    print(f"Answers loaded from {args.faq.name} ({len(bot.faqs)} questions).")
    print_responses([bot.welcome()])
    try:
        while bot.state != "exit":
            print_responses(bot.reply(input("\nYou: ")))
    except (EOFError, KeyboardInterrupt):
        print("\nBot: Goodbye! Thanks for chatting.")
        bot.state = "exit"
    return 0


if __name__ == "__main__":
    sys.exit(main())
