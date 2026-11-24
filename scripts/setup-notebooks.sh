#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
provider="${XDG_DATA_HOME:-$HOME/.local/share}/nvim/notebook-provider"
command -v uv >/dev/null
command -v nvim >/dev/null
if [[ ! -x "$provider/bin/python" ]]; then
  uv venv --python "${NOTEBOOK_PROVIDER_PYTHON:-python3}" "$provider"
fi
"$provider/bin/python" -c 'import sys; assert sys.version_info >= (3, 10), "Molten requires Python >=3.10"'
uv pip install --python "$provider/bin/python" -r "$root/scripts/notebook-provider-requirements.txt"
if [[ "${1:-}" == "--rich" ]]; then
  uv pip install --python "$provider/bin/python" -r "$root/scripts/notebook-rich-requirements.txt"
fi
if [[ "$(readlink -f "$HOME/.config/nvim")" != "$root" ]]; then
  printf 'Expected ~/.config/nvim to resolve to %s; review your symlink before continuing.\n' "$root" >&2
  exit 1
fi
# The Molten build applies pinned compatibility/safety fixes and registers rplugins.
nvim --headless '+Lazy! install' '+Lazy! build molten-nvim' '+qa!'
