#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THIRD_PARTY_DIR="$ROOT_DIR/third_party"
ANYTEXT2_DIR="$THIRD_PARTY_DIR/AnyText2"
ENV_NAME="anytext2"
UPSTREAM_URL="https://github.com/tyxsspa/AnyText2.git"
ANYTEXT2_REV="${ANYTEXT2_REV:-b06c583a583818f3679665ef67b51363f107853c}"

command -v git >/dev/null 2>&1 || { echo "ERROR: git not found"; exit 1; }
command -v conda >/dev/null 2>&1 || { echo "ERROR: conda not found"; exit 1; }

mkdir -p "$THIRD_PARTY_DIR"

if [[ ! -d "$ANYTEXT2_DIR/.git" ]]; then
  git clone "$UPSTREAM_URL" "$ANYTEXT2_DIR"
fi

git -C "$ANYTEXT2_DIR" fetch --all --tags
git -C "$ANYTEXT2_DIR" checkout --detach "$ANYTEXT2_REV"

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "[SynSLP] Updating existing conda env: $ENV_NAME"
  conda env update -n "$ENV_NAME" -f "$ANYTEXT2_DIR/environment.yaml" --prune
else
  echo "[SynSLP] Creating conda env from upstream environment.yaml"
  conda env create -f "$ANYTEXT2_DIR/environment.yaml"
fi

echo "[SynSLP] Downloading official AnyText2 checkpoint: iic/cv_anytext2"
export ANYTEXT2_DIR
conda run -n "$ENV_NAME" python - <<'PY'
import os
import shutil
from pathlib import Path
from modelscope import snapshot_download

dst = Path(os.environ["ANYTEXT2_DIR"]) / "models"
dst.mkdir(parents=True, exist_ok=True)

src = Path(snapshot_download("iic/cv_anytext2"))
for item in src.iterdir():
    target = dst / item.name
    if item.is_dir():
        shutil.copytree(item, target, dirs_exist_ok=True)
    else:
        shutil.copy2(item, target)

ckpt = dst / "anytext_v2.0.ckpt"
if not ckpt.exists():
    raise FileNotFoundError(f"Expected checkpoint not found: {ckpt}")

print(f"[SynSLP] checkpoint ready: {ckpt}")
PY

echo
echo "[SynSLP] AnyText2 deployment files are ready."
echo "Next: bash scripts/check_anytext2.sh"
