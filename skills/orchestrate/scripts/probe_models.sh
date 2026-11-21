#!/usr/bin/env bash
# Probe each candidate worker model with a real one-line call, and print one JSON line per model.
#
#   probe_models.sh [harness:model ...]   default: every chain in SKILL.md step 2
#
# harness is pi (default), claude (Claude Code) or gemini (the Gemini CLI, headless).
#
# Each line looks like {"model": ..., "harness": ..., "live": true|false, "detail": ...}.
# `pi auth check` alone is not enough: it reported "ready" for an opencode-go key that had
# expired, and for an Anthropic OAuth plan that refuses third-party apps. Only a real call
# shows a model is usable. Each probe costs a handful of tokens.
set -uo pipefail

DEFAULT=(
  # implementer
  "pi:opencode-go/kimi-k3.1-pro"
  "claude:claude-sonnet-5-5"
  # escalation implementer
  "claude:claude-opus-5-5"
  # reviewer
  "pi:openai-codex/gpt-6.2-sol"
  "pi:openai-codex/gpt-6.2-astra"
  # owner survey
  "claude:claude-haiku-5-5"
  "gemini:gemini-3.8-flash"
  # opt-in cheap lane
  "pi:opencode-go/glm-5.3-flash"
  "pi:opencode-go/deepseek-v4.1-flash"
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
  elif [[ $harness == gemini ]]; then
    # Headless Gemini refuses an untrusted directory unless told to trust it. Its keyring
    # and ripgrep notices go to the same stream, so keep only the last real line.
    out=$(GEMINI_CLI_TRUST_WORKSPACE=true timeout 120 gemini -m "$model" -p "Reply with exactly: OK" 2>&1 \
      | grep -v -e 'secret service' -e 'Ripgrep is not available' | tail -3)
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
