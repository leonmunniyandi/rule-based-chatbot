# Rule-Based Interactive Terminal Chatbot

A Python console assistant that answers questions using the supplied
`sample_faq.json`. Built for Task 4.

## Features

- Greetings loaded from the supplied JSON file.
- Case and punctuation normalization with regular expressions.
- Exact-question and keyword/regex matching.
- Multiple topic matches in one message, with each matching FAQ answered once.
- Follow-up context, a numbered help menu, and repeat commands.
- Helpful fallbacks for empty or unrecognized input.
- Clean exits using `bye`, `exit`, `quit`, EOF, or Ctrl+C.
- Clear errors for missing, malformed, or incorrectly structured JSON.

## Requirements

Python 3.9 or later. Only the standard library is used, so no packages,
internet access, or API key are required.

Keep `chatbot.py` and `sample_faq.json` in the same folder.

## Run

Open a terminal in this folder:

```bash
python chatbot.py
```

The JSON file is located relative to the script, so launching the script from
another working directory also works.

## Included topics

The supplied sample data covers:

- Business hours: the sample answer lists Monday-Friday, 9 AM-6 PM IST.
- Internship project submission: a public GitHub repository link through Student Workspace.
- Certificates: the sample answer lists 3-5 business days after code review.

These answers are demonstration content from your dataset. They are displayed
as supplied and are not independently verified business policies. Customize
the JSON before using the bot for another organization.

## Example conversation

```text
You: Hi!
Bot: Hello! How can I help?

You: What are your hours and how do I submit my project?
Bot: We operate Monday through Friday from 9:00 AM to 6:00 PM IST.
Bot: You can submit your public GitHub repository link through your Student Workspace.

You: When will I receive my certificate?
Bot: Certificates are reviewed and issued within 3-5 business days after your code review.

You: How long does that take?
Bot: Certificates are reviewed and issued within 3-5 business days after your code review.

You: bye
Bot: Goodbye! Thanks for chatting.
```

## Commands and context

| Input | Behavior |
| --- | --- |
| `help`, `menu`, or `faq` | Show numbered FAQ questions |
| A valid question number, such as `1` | Answer that question |
| `repeat` or `again` | Repeat the last matched answer(s) |
| `how long does that take?` | Repeat certificate timing after a single certificate topic |
| `where do I send it?` | Repeat submission instructions after a single submission topic |
| `bye`, `exit`, or `quit` | End the conversation |

Exit commands must be the entire message, ignoring case and punctuation.
For example, `how do I quit my internship?` does not end the chat.

An ambiguous follow-up asks the user to choose a topic. An unrelated question
clears earlier topic context. The bot does not guess unsupported answers.

## How matching works

The bot recognizes the three supplied topics with built-in keyword and regex
rules. Exact questions always match. Additional FAQ questions can match by
exact wording or sufficient nontrivial word overlap. The matching rules live
in `match_intents` in `chatbot.py` and can be extended for new topic wording.

This is a rule-based assistant: it has no general language model, and a topic
keyword can select a stored answer even if the question asks for a detail that
is not in that answer. It returns the available FAQ text rather than inventing
that detail.

Conversation state tracks greeting, awaiting a query, resolution,
clarification, and exit. Context lasts only for the current program run.

## Customize the data

```json
{
  "greetings": ["hello", "hi", "hey"],
  "faqs": [
    {
      "question": "What are your opening hours?",
      "answer": "Your business hours here."
    }
  ]
}
```

Use non-empty strings and unique questions. To load a different file:

```bash
python chatbot.py --faq my_faq.json
```

## Tests

```bash
python -m unittest -v
```

The tests cover intent matching, multiple topics, follow-up context, exits,
fallbacks, JSON validation, and the console loop.

## Files

- `chatbot.py`: main program.
- `sample_faq.json`: original supplied dataset, preserved unchanged.
- `test_chatbot.py`: automated tests.
- `README.md`: instructions and examples.
- `.gitignore`: excludes local Python environments and caches.
