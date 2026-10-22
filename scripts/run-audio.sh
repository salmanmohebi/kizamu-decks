#!/usr/bin/env bash
# Run an audio generator with one process per GPU, then merge the shards.
#
#   scripts/run-audio.sh german.grammar.audio [extra generate options]
#   KE_LEVEL=C1 scripts/run-audio.sh english.audio
#   scripts/run-audio.sh german.vocab.audio_cuda --batch-size 32
#
# GPUS sets the number of processes (default: all GPUs that nvidia-smi lists).
# Logs go to $KIZAMU_DATA/logs/ (default data/logs/).
set -uo pipefail
module="${1:?usage: scripts/run-audio.sh <module> [generate options]}"
shift
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
gpus="${GPUS:-$(nvidia-smi -L 2>/dev/null | wc -l)}"
if [ "$gpus" -lt 1 ]; then
    echo "no GPU found (set GPUS to override)" >&2
    exit 1
fi
logs="${KIZAMU_DATA:-$root/data}/logs"
mkdir -p "$logs"
export TOKENIZERS_PARALLELISM=false
pids=()
for ((index = 0; index < gpus; index++)); do
    CUDA_VISIBLE_DEVICES="$index" uv run --group gpu python -m "$module" generate \
        --shard-index "$index" --shard-count "$gpus" "$@" \
        >"$logs/${module//./-}-shard-$index.log" 2>&1 &
    pids+=("$!")
done
status=0
for pid in "${pids[@]}"; do wait "$pid" || status=1; done
if [ "$status" -ne 0 ]; then
    echo "a shard failed, see $logs/" >&2
    exit "$status"
fi
uv run --group gpu python -m "$module" merge --shard-count "$gpus"
