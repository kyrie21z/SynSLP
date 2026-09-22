#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANYTEXT2_DIR="$ROOT_DIR/third_party/AnyText2"
ENV_NAME="anytext2"

if ! command -v conda >/dev/null 2>&1; then
  for candidate in "/mnt/data/zyx/miniconda3/bin" "$HOME/miniconda3/bin" "$HOME/anaconda3/bin"; do
    if [[ -x "$candidate/conda" ]]; then
      export PATH="$candidate:$PATH"
      break
    fi
  done
fi

[[ -d "$ANYTEXT2_DIR" ]] || { echo "ERROR: $ANYTEXT2_DIR not found. Run scripts/setup_anytext2.sh first."; exit 1; }

cd "$ANYTEXT2_DIR"

ARGS=()
if [[ "${USE_TRANSLATOR:-0}" != "1" ]]; then
  # Upstream notes that the CH->EN image-prompt translator costs ~4 GB VRAM.
  # Target Chinese strings inside quoted text prompts still work without it.
  ARGS+=(--no_translator)
fi

if [[ "${GRADIO_LISTEN:-0}" == "1" ]]; then
  export GRADIO_LISTEN=1
fi

exec conda run --no-capture-output -n "$ENV_NAME" python demo.py "${ARGS[@]}" "$@"
