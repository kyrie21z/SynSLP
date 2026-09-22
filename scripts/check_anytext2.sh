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
[[ -f "$ANYTEXT2_DIR/models/anytext_v2.0.ckpt" ]] || { echo "ERROR: AnyText2 checkpoint not found."; exit 1; }

cd "$ANYTEXT2_DIR"

conda run --no-capture-output -n "$ENV_NAME" python - <<'PY'
import torch

print(f"torch={torch.__version__}")
print(f"cuda_available={torch.cuda.is_available()}")
if not torch.cuda.is_available():
    raise SystemExit("ERROR: CUDA is not available inside the anytext2 environment.")

name = torch.cuda.get_device_name(0)
vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
print(f"gpu={name}")
print(f"vram_gb={vram_gb:.2f}")

from ms_wrapper import AnyText2Model

model = AnyText2Model(
    model_dir="./models",
    use_fp16=True,
    use_translator=False,
    font_path="font/Arial_Unicode.ttf",
    model_path="models/anytext_v2.0.ckpt",
).cuda(0)

print("ANYTEXT2_SMOKE_TEST=PASS")
PY
