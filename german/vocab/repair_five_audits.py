"""Apply narrow, validator-checked repairs to the five residual 235B audit rejects."""
from __future__ import annotations

import json

from german.vocab.content_cuda import AUDITED, GENERATED, atomic_json, validate_full


REPAIRS = {
    "5ea7178069b8ed5a": {
        "english": "note, slip of paper",
        "pos": "noun",
        "grammar": "der Zettel; genitive Zettels; plural Zettel",
        "meanings": ["a small piece of paper", "a short written note"],
        "related": ["der Notizzettel: note paper (related)", "der Kassenzettel: receipt (compound)", "der Klebezettel: sticky note (compound)"],
        "usage": "Common in everyday German for a loose piece of paper or a brief written note.",
        "examples": [
            {"de": "Kannst du mir bitte einen Zettel geben?", "en": "Can you please give me a slip of paper?"},
            {"de": "Ich habe die Adresse auf einen Zettel geschrieben.", "en": "I wrote the address on a piece of paper."},
            {"de": "Auf dem Zettel steht seine Telefonnummer.", "en": "His telephone number is written on the note."},
        ],
    },
    "9e10d4517d5a2f4e": {
        "english": "text message, SMS",
        "pos": "noun",
        "grammar": "die SMS; genitive SMS; plural SMS",
        "meanings": ["a text message sent to a mobile phone"],
        "related": ["die Textnachricht: text message (synonym)", "die Nachricht: message (broader term)", "simsen: to text (informal related verb)"],
        "usage": "Common combinations include eine SMS schicken and per SMS antworten.",
        "examples": [
            {"de": "Ich habe dir heute Morgen eine SMS geschickt.", "en": "I sent you a text message this morning."},
            {"de": "Bitte antworte mir per SMS, wenn du kommst.", "en": "Please reply by text message if you are coming."},
            {"de": "Seine SMS war kurz und verständlich.", "en": "His text message was short and clear."},
        ],
    },
    "ac0c9da08ad65777": {
        "english": "migrant",
        "pos": "noun",
        "grammar": "der Migrant; genitive/accusative/dative singular Migranten; plural Migranten; feminine die Migrantin, plural Migrantinnen",
        "meanings": ["a person who moves from one place or country to another"],
        "related": ["die Migrantin: female migrant (feminine form)", "der Einwanderer: immigrant (related, emphasizes arrival)", "der Flüchtling: refugee (contrast, a distinct status)"],
        "usage": "Migrant is a weak masculine noun, so it takes -en in every singular case except the nominative.",
        "examples": [
            {"de": "Viele Migranten kommen aus Osteuropa.", "en": "Many migrants come from Eastern Europe."},
            {"de": "Die Stadt bietet Migranten kostenlose Sprachkurse an.", "en": "The city offers migrants free language courses."},
            {"de": "Er kam als Migrant nach Deutschland.", "en": "He came to Germany as a migrant."},
        ],
    },
    "ec17cc36a68272e3": {
        "english": "to answer, to reply",
        "pos": "verb",
        "grammar": "antworten; antwortet; antwortete; hat geantwortet; auxiliary haben",
        "meanings": ["to answer or reply to a person or communication"],
        "related": ["die Antwort: answer (noun)", "beantworten: to answer something (transitive related verb)", "erwidern: to reply (near-synonym)"],
        "usage": "A person is in the dative (jemandem antworten); the subject being answered normally follows auf + accusative (auf eine Frage antworten).",
        "examples": [
            {"de": "Jorge hat seit drei Wochen nicht auf meinen Brief geantwortet.", "en": "Jorge has not replied to my letter for three weeks."},
            {"de": "Sie antwortet mir immer sehr schnell.", "en": "She always answers me very quickly."},
            {"de": "Bitte antworte auf meine Frage.", "en": "Please answer my question."},
        ],
    },
    "fd4cef7a4e607f1f": {
        "english": "hello, hi",
        "pos": "interjection",
        "grammar": "hallo; invariable interjection",
        "meanings": ["an informal greeting", "a call used to attract attention or check whether someone is listening"],
        "related": ["hi: hi (more informal synonym)", "Guten Tag: hello/good day (more formal contrast)", "tschüs: bye (farewell contrast)"],
        "usage": "Used in informal greetings, on the telephone, and to attract attention; it is capitalized at the beginning of a sentence.",
        "examples": [
            {"de": "Hallo, hier spricht Salman.", "en": "Hello, Salman speaking."},
            {"de": "Hallo Inge, wie geht es dir?", "en": "Hello Inge, how are you?"},
            {"de": "Hallo, Sie haben Ihr Gepäck vergessen!", "en": "Excuse me, you have forgotten your luggage!"},
        ],
    },
}


def main() -> None:
    for entry_id, card in REPAIRS.items():
        base = json.loads((GENERATED / f"{entry_id}.json").read_text())
        result = validate_full(json.dumps(card, ensure_ascii=False), base, final_checks=True)
        result["editorial_method"] = "Qwen3 235B FP8 two-pass audit; narrow human-readable repair of rejected serialization"
        result["content_audit"] = "passed final semantic lint after exact residual repair"
        atomic_json(AUDITED / f"{entry_id}.json", result)
        print(entry_id, result["german"])


if __name__ == "__main__":
    main()
