#!/usr/bin/env bash
# Probe each candidate worker model with a real one-line call, and print one JSON line per model.
#
#   probe_models.sh [model ...]     default: the implementer and reviewer chains
#
# Each line looks like {"model": ..., "harness": ..., "live": true|false, "detail": ...}.
# `pi auth check` alone is not enough: it reported "ready" for an opencode-go key that had
# expired, and for an Anthropic OAuth plan that refuses third-party apps. Only a real call
# shows a model is usable. Each probe costs a handful of tokens.
set -uo pipefail

DEFAULT=(
  "pi:opencode-go/deepseek-v4.1-flash"
  "pi:deepseek/deepseek-flash"
  "claude:claude-haiku-5-5"
  "pi:openai-codex/gpt-6.1-sol"
)
CANDIDATES=("${@:-${DEFAULT[@]}}")
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK" || exit 1

probe() {
  local harness=${1%%:*} model=${1#*:} out
  if [[ $1 != *:* ]]; then harness=pi; model=$1; fi
  if [[ $harness == claude ]]; then
    out=$(timeout 120 claude -p --model "$model" "Reply with exactly: OK" 2>&1 | tail -3)
  else
    out=$(timeout 120 pi -p --model "$model" --no-session --no-context-files --no-skills \
      --no-extensions "Reply with exactly: OK" 2>&1 | tail -3)
  fi
  local live=false
  grep -qx 'OK' <<<"$(tr -d '[:space:]' <<<"$out")" && live=true
  python3 - "$model" "$harness" "$live" "$out" <<'PY'
import json, sys
model, harness, live, out = sys.argv[1:]
print(json.dumps({"model": model, "harness": harness, "live": live == "true",
                  "detail": " ".join(out.split())[:200]}))
PY
}

for candidate in "${CANDIDATES[@]}"; do
  probe "$candidate" &
done
wait
