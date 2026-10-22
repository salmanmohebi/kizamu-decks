# kizamu-decks

Anki decks with audio for language learning, and the pipeline that builds them.

| Deck | What it is | Docs |
|---|---|---|
| `kizamu-german::vocab` | German vocabulary A1, A2, B1: both directions, forms, usage, 3 examples per word | [german/vocab](german/vocab/README.md) |
| `kizamu-german::grammar` | German grammar A1–B2 + 22 hard topics: fill-the-gap and drills, an explanation on every card | [german/grammar](german/grammar/README.md) |
| `kizamu-german::sentences` | Whole sentences English → Deutsch, listening, situational phrases | [german/grammar](german/grammar/README.md) |
| `kizamu-english::C1`, `::C2` | American English for advanced learners: 3,000 notes per level in 60 decks | [english](english/README.md) |

All audio is synthetic (Qwen3-TTS VoiceDesign) and checked with Whisper: a clip whose
transcript does not match its text is generated again. All content was written and
reviewed in separate passes and validated by scripts.

## Layout

```
german/vocab/     code + entries.json (the vocabulary content)
german/grammar/   code + content/ (one JSON file per topic) + authoring guides
english/          code + C1/, C2/ (selection, content, catalogue) + guides
kizamu/           paths.py (where the code finds the data folder), publishing tools
scripts/          run-audio.sh: one audio process per GPU
```

Git holds only the code and the hand-written content. Everything the pipelines generate
(audio, Anki profiles, packages, model outputs) goes to the **data folder**:
`$KIZAMU_DATA`, or `data/` in the repository when the variable is not set. Its layout:

```
$KIZAMU_DATA/
  german/vocab/    build/ (source.anki21, profiles, content stages), audio/qwen/, out/, out-kizamu/, pilot/
  german/grammar/  build/ (inputs, legacy.json, profile), audio/qwen/, out/, legacy-notes/
  english/         shared/ (evidence pool), audio/qwen/, C1/{build,out}, C2/{build,out}
  logs/
```

## Python environment

The project uses [uv](https://docs.astral.sh/uv/) and Python 3.11.

```bash
# 1. Install uv (once)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create the environment: validators, deck builds and checks
uv sync

# 3. Optional extras
uv sync --group gpu     # audio (Qwen3-TTS + Whisper) and content generation; needs an NVIDIA GPU
uv sync --group mac     # pilot audio and drafts on Apple Silicon (MLX)
```

`uv sync` creates `.venv/` in the repository. To keep the environment somewhere else,
set `UV_PROJECT_ENVIRONMENT` first. uv then creates and uses the environment there:

```bash
export UV_PROJECT_ENVIRONMENT=/path/to/envs/kizamu-decks
uv sync --group gpu
```

The content audit (`german.vocab.content_audit`) needs vLLM, which pins a different
Torch/Transformers stack, so it runs in a second environment:

```bash
uv venv --python 3.11 .venv-vllm
uv pip install --python .venv-vllm -r requirements-vllm.txt
.venv-vllm/bin/python -m german.vocab.content_audit --tensor-parallel-size <number of GPUs>
```

Run everything from the repository root, with `uv run python -m <module>` or the
Makefile. The validators use only the standard library and PyYAML.

Other tools: `zstd` (only to read newer `.colpkg` backups) and `nvidia-smi` (to count
GPUs in `scripts/run-audio.sh`). Models download from Hugging Face on first use into
the normal Hugging Face cache (set `HF_HOME` to move it):

| Model | Used for |
|---|---|
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | all audio |
| `openai/whisper-large-v3-turbo` | audio check |
| `Qwen/Qwen3-30B-A3B-Instruct-2507` | vocabulary content |
| `Qwen/Qwen3-235B-A22B-Instruct-2507-FP8` | vocabulary content audit |

## Build

```bash
export KIZAMU_DATA=/path/to/kizamu-data
make validate                  # check all content
make vocab-audio grammar-audio # audio, one process per GPU (only new or changed clips)
make vocab                     # → $KIZAMU_DATA/german/vocab/out-kizamu/
make grammar                   # → $KIZAMU_DATA/german/grammar/out/
make english KE_LEVEL=C1       # → $KIZAMU_DATA/english/C1/out/  (english-audio for its audio)
```

Build in this order: vocab, grammar, english. Each build reads the Anki profiles of the
builds before it, so that no two decks use the same review IDs.

## Publishing

The decks are published in
[kizamu-decks-releases](https://github.com/salmanmohebi/kizamu-decks-releases) (packages
in the releases, preview pages in `docs/`) and the audio in the Hugging Face dataset
[salmanmohebi/kizamu-audio](https://huggingface.co/datasets/salmanmohebi/kizamu-audio).

```bash
make public                         # → $KIZAMU_DATA/public/: packages without history + SHA256SUMS
make previews PREVIEWS=<docs folder> # one page per package with sample cards and real audio
make public-audio                   # → $KIZAMU_DATA/public-audio/: one zip + metadata.csv per deck family
hf upload salmanmohebi/kizamu-audio $KIZAMU_DATA/public-audio . --repo-type dataset --exclude export-report.json
```

The dataset card is [kizamu/hf-dataset-card.md](kizamu/hf-dataset-card.md);
`export_audio` copies it to `public-audio/README.md`. The packages go into a new release
of kizamu-decks-releases, the previews into its `docs/` folder.

## Review history

The current builds start from a snapshot of an existing Anki collection
(`$KIZAMU_DATA/german/vocab/build/source.anki21`). Where a new card replaces an old card
that was studied, the build copies the old card's schedule, FSRS state and review
records onto the new card. These packages are named `*-WITH-HISTORY.apkg`. They contain
personal review data, so they are not for sharing.

`make public` makes the shareable copies in `$KIZAMU_DATA/public/`: every package is
imported into an empty collection without scheduling and exported again with media and
deck presets. All cards are new, there are no review records, and the FSRS parameters
of the presets are the defaults. Each file is checked by a second import.
