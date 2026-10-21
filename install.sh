#!/usr/bin/env bash
# Link this clone's skills into ~/.agents/skills, and ~/.claude/skills into those,
# the same layout `npx skills add -g` produces. Edits in the clone take effect at once.
set -euo pipefail

repo=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"

link() { # target link-path
  if [ -e "$2" ] && [ ! -L "$2" ]; then
    echo "skip $2: a real directory is there; move it aside and re-run"
    return
  fi
  ln -sfn "$1" "$2"
  echo "$2 -> $1"
}

for dir in "$repo"/skills/*/; do
  name=$(basename "$dir")
  link "$repo/skills/$name" "$HOME/.agents/skills/$name"
  link "../../.agents/skills/$name" "$HOME/.claude/skills/$name"
done
