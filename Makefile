# kizamu-decks. Generated data goes to $KIZAMU_DATA (default: data/).
# Build order: vocab → grammar → english (each build reads the profiles of the builds before it).
.PHONY: validate vocab-base vocab-audio vocab grammar-audio grammar english-audio english public previews public-audio

RUN := uv run python -m
KE_LEVEL ?= C2

validate:
	$(RUN) german.grammar.validate --all
	KE_LEVEL=C1 $(RUN) english.validate --all
	KE_LEVEL=C2 $(RUN) english.validate --all

# German vocabulary: the base build over the source collection, then the kizamu packages.
vocab-base:
	$(RUN) german.vocab.build_base
	$(RUN) german.vocab.check_base

vocab-audio:
	scripts/run-audio.sh german.vocab.audio_cuda --batch-size 32

vocab:
	$(RUN) german.vocab.build
	$(RUN) german.vocab.check

# German grammar + sentences
grammar-audio:
	scripts/run-audio.sh german.grammar.audio --batch-size 24

grammar:
	$(RUN) german.grammar.validate --all
	$(RUN) german.grammar.build
	$(RUN) german.grammar.check
	$(RUN) german.grammar.preview

# American English, one level at a time: make english KE_LEVEL=C1
english-audio:
	KE_LEVEL=$(KE_LEVEL) scripts/run-audio.sh english.audio

english:
	KE_LEVEL=$(KE_LEVEL) $(RUN) english.validate --all
	KE_LEVEL=$(KE_LEVEL) $(RUN) english.build
	KE_LEVEL=$(KE_LEVEL) $(RUN) english.check
	KE_LEVEL=$(KE_LEVEL) $(RUN) english.preview --embed-audio

# Publishing: shareable packages (no review history), preview pages, audio zips
public:
	$(RUN) kizamu.export_public

PREVIEWS ?= $(or $(KIZAMU_DATA),data)/previews
previews:
	$(RUN) kizamu.preview_public --out $(PREVIEWS)

public-audio:
	$(RUN) kizamu.export_audio
