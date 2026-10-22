# kizamu-german · vocabulary (A1, A2, B1)

Anki decks `kizamu-german::vocab::A1 | A2 | B1`. One note per word or sense, two cards
(Deutsch → English and English → Deutsch). The answer shows forms and grammar, the
meaning, related words and contrasts, usage notes and three translated examples. German
nouns come with the article; short cues separate words with the same spelling
(`die Bank` the bank vs. the bench). The word and every example have audio.

The source of truth is [entries.json](entries.json): one record per note, with the
level, the source note, the forms, the examples and the dictionary data.

## Pipeline

```bash
python -m german.vocab.source extract --collection <backup.colpkg>  # source decks → build/source-notes.json
python -m german.vocab.source dictionary     # filtered Wiktionary cache (kaikki.org) → build/dictionary.json
python -m german.vocab.content prepare       # non-overlapping groups → build/groups.json
# content: one process per GPU, then an independent audit with a larger model
python -m german.vocab.content_cuda generate --shard-index <i> --shard-count <n>
python -m german.vocab.content_audit         # in the vLLM environment, see the main README
python -m german.vocab.content_cuda promote  # audited entries → entries.json
scripts/run-audio.sh german.vocab.audio_cuda --batch-size 32   # Qwen3-TTS, one process per GPU, then merge
make vocab-base                              # base build over the source collection + checks
make vocab                                   # kizamu packages + import check
```

`content` and `editor` (`draft`, `edit`) are the same steps with small local models on
Apple Silicon (the `mac` dependency group). The `pilot_*` modules built and checked the
20-entry pilot that fixed the card design and the voice; `audio` reuses its approved
clips. `repair_five_audits` is the one-off fix of the last five audit rejects.

## Review history

`build_base` works on a copy of the source collection: it builds the decks and copies
each old card's schedule, FSRS state and review records. `build` then makes the
side-by-side packages (`kizamu-german-vocab-<level>-WITH-HISTORY.apkg`): new note and
card identities, with the history copied onto the new cards, so the old cards stay as
they were. Import steps: [IMPORT.md](IMPORT.md).
