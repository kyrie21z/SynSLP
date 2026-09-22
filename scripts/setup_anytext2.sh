#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THIRD_PARTY_DIR="$ROOT_DIR/third_party"
ANYTEXT2_DIR="$THIRD_PARTY_DIR/AnyText2"
ENV_NAME="anytext2"
UPSTREAM_URL="https://github.com/tyxsspa/AnyText2.git"
ANYTEXT2_REV="${ANYTEXT2_REV:-b06c583a583818f3679665ef67b51363f107853c}"
PATCH_FILE="$ROOT_DIR/patches/anytext2/0001-anytext2-compatibility.patch"
COMPAT_REQ="$ROOT_DIR/scripts/requirements-anytext2-compat.txt"

# Locate conda if running under non-interactive SSH
if ! command -v conda >/dev/null 2>&1; then
  for candidate in "/mnt/data/zyx/miniconda3/bin" "$HOME/miniconda3/bin" "$HOME/anaconda3/bin"; do
    if [[ -x "$candidate/conda" ]]; then
      export PATH="$candidate:$PATH"
      break
    fi
  done
fi

command -v git >/dev/null 2>&1 || { echo "ERROR: git not found"; exit 1; }
command -v conda >/dev/null 2>&1 || { echo "ERROR: conda not found"; exit 1; }

mkdir -p "$THIRD_PARTY_DIR"

# 1. Clone or fetch pinned upstream commit
if [[ ! -d "$ANYTEXT2_DIR/.git" ]]; then
  echo "[SynSLP] Cloning upstream AnyText2..."
  git clone "$UPSTREAM_URL" "$ANYTEXT2_DIR"
fi

echo "[SynSLP] Checking out pinned AnyText2 commit: $ANYTEXT2_REV"
git -C "$ANYTEXT2_DIR" fetch --all --tags
git -C "$ANYTEXT2_DIR" checkout --detach "$ANYTEXT2_REV"

# 2. Idempotently apply repository-controlled compatibility patch
if [[ -f "$PATCH_FILE" ]]; then
  if git -C "$ANYTEXT2_DIR" apply --check "$PATCH_FILE" >/dev/null 2>&1; then
    echo "[SynSLP] Applying compatibility patch: $(basename "$PATCH_FILE")"
    git -C "$ANYTEXT2_DIR" apply "$PATCH_FILE"
  elif git -C "$ANYTEXT2_DIR" apply -R --check "$PATCH_FILE" >/dev/null 2>&1; then
    echo "[SynSLP] Compatibility patch already applied: $(basename "$PATCH_FILE")"
  else
    echo "ERROR: Compatibility patch cannot be applied cleanly to AnyText2."
    exit 1
  fi
else
  echo "ERROR: Compatibility patch not found at $PATCH_FILE"
  exit 1
fi

# 3. Create or update isolated conda environment
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "[SynSLP] Using existing conda env: $ENV_NAME"
else
  echo "[SynSLP] Creating conda env from upstream environment.yaml"
  conda env create -f "$ANYTEXT2_DIR/environment.yaml"
fi

# 4. Enforce CUDA-enabled PyTorch build and compatibility pins
echo "[SynSLP] Ensuring CUDA-enabled PyTorch 2.1.0..."
if ! conda run -n "$ENV_NAME" python -c "import torch; assert torch.cuda.is_available()" >/dev/null 2>&1; then
  echo "[SynSLP] Reinstalling PyTorch with CUDA 12.1..."
  conda run -n "$ENV_NAME" python -m pip install torch==2.1.0+cu121 torchvision==0.16.0+cu121 --extra-index-url https://download.pytorch.org/whl/cu121
fi

if [[ -f "$COMPAT_REQ" ]]; then
  echo "[SynSLP] Enforcing verified compatibility package pins..."
  conda run -n "$ENV_NAME" python -m pip install -r "$COMPAT_REQ"
fi

# 5. Download and verify official checkpoint
echo "[SynSLP] Downloading/verifying official AnyText2 checkpoint: iic/cv_anytext2"
export ANYTEXT2_DIR
conda run -n "$ENV_NAME" python - <<'PY'
import os
import shutil
from pathlib import Path
from modelscope import snapshot_download

dst = Path(os.environ["ANYTEXT2_DIR"]) / "models"
dst.mkdir(parents=True, exist_ok=True)

ckpt = dst / "anytext_v2.0.ckpt"
if not ckpt.exists():
    print("[SynSLP] Checkpoint not found locally. Downloading from ModelScope...")
    src = Path(snapshot_download("iic/cv_anytext2"))
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

if not ckpt.exists():
    raise FileNotFoundError(f"Expected checkpoint not found: {ckpt}")

print(f"[SynSLP] Checkpoint ready: {ckpt} ({ckpt.stat().st_size / (1024**3):.2f} GB)")
PY

echo
echo "[SynSLP] AnyText2 deployment files and environment are ready."
echo "Next: bash scripts/check_anytext2.sh"
