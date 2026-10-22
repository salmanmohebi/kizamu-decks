---
license: cc-by-sa-4.0
language:
- de
- en
pretty_name: kizamu audio
size_categories:
- 10K<n<100K
task_categories:
- text-to-speech
tags:
- anki
- language-learning
- synthetic-speech
- german
- american-english
---

# kizamu audio

The audio of the [kizamu Anki decks](https://github.com/salmanmohebi/kizamu-decks-releases):
54,898 synthetic speech clips (about 49 hours) of German and American English words,
example sentences and phrases for language learners.

| File | Clips | Hours | Size | Voice |
|---|---|---|---|---|
| `german-vocab.zip` | 11,567 | 7.9 | 240 MB | German, adult male |
| `german-grammar.zip` | 13,688 | 10.4 | 315 MB | German, adult male (grammar and sentence decks) |
| `english.zip` | 29,643 | 31.2 | 875 MB | American English, adult female (C1 and C2 decks) |

Each zip contains the MP3 files and a `metadata.csv`. The same `metadata.csv` is also
next to each zip (`<name>-metadata.csv`), so you can read it without unpacking.

## Metadata

| Column | Meaning |
|---|---|
| `file_name` | the MP3 file |
| `text` | the text as it is shown on the card |
| `spoken_text` | the text given to the speech model (abbreviations written out, for example) |
| `language` | `German` or `English` |
| `voice` | the voice description given to the model |
| `seconds` | length of the clip |
| `asr_transcript` | Whisper transcript of the clip (empty for most vocabulary clips) |
| `asr_match` | `True` when the transcript matches the text |

## How the clips were made

All clips were generated with
[Qwen3-TTS-12Hz-1.7B-VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)
from the voice descriptions in the `voice` column (temperature 0.65, top-p 0.9). Clips
were transcribed with
[Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo); a clip
whose transcript did not match the text was generated again with another seed
(`asr_match` shows the result of the last check). Whisper cannot judge word stress,
intonation or vowel quality, so a few clips may still sound wrong.

The speech is synthetic. No recordings of real people were used.

## License

[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), like the decks.
