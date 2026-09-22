# Agent Status: SynSLP AnyText2 Deployment & Multi-End Sync

Updated: 2026-09-22T06:25:00.000Z
Status: COMPLETED (REPRODUCIBILITY GAPS CLOSED & 3-END GIT SYNCHRONIZED)

## Overview
Successfully executed all requirements defined in `.ai-bridge/current-plan.md` using the RGSLPR-compatible SSH approach (`ssh -o ClearAllForwardings=yes server-zyx`):
1. **Reproducibility Gaps Closed**: Encoded all server compatibility fixes and dependency pins into repository-tracked assets.
2. **Deterministic Setup Automation**: Updated `scripts/setup_anytext2.sh` to clone/checkout pinned commit `b06c583`, apply compatibility patch idempotently, ensure CUDA PyTorch, enforce pinned requirements, and download/verify ModelScope weights.
3. **Multi-End Git Consistency**: Local working tree, GitHub `origin/main`, and `server-zyx` working tree are cleanly synchronized to the exact same commit.
4. **End-to-End Verification**: Clean-checkout patch application, idempotent setup rerun, `check_anytext2.sh`, and full `smoke_test_anytext2.py` (stock edit + SLP edit) all verified passing on NVIDIA GeForce RTX 4090.

---

## 3-End Git Consistency

- **Commit**: `5763f231381eaaf554a3ba07f39352e9dce8813e` (and subsequent documentation commit)
- **Local HEAD**: Matches `origin/main`
- **GitHub origin/main**: Up to date
- **server-zyx HEAD**: Matches `origin/main`
- **Tracked Working Tree**: Clean on both local and `server-zyx`.
- **Untracked Policy**: `third_party/`, `outputs/`, checkpoints, and conda environments remain properly untracked.

---

## Tracked Reproducibility Assets Added/Updated

### 1. `patches/anytext2/0001-anytext2-compatibility.patch`
Minimal 2-hunk compatibility patch against upstream AnyText2 commit `b06c583a583818f3679665ef67b51363f107853c`:
- `ldm/modules/attention.py`: Casts softmax similarity to `v.dtype` (`sim = sim.softmax(dim=-1).to(v.dtype)`) to eliminate `RuntimeError: expected scalar type Half but found Float` during FP16 inference in fallback `CrossAttention` without `xformers`.
- `ms_wrapper.py`: Adds defensive default sort order (`fir, sec = 0, 1`) when `sort_priority` is neither `'↕'` nor `'↔'` to prevent unbound variable `NameError`.

### 2. `scripts/requirements-anytext2-compat.txt`
Strictly pins and constrains runtime packages verified on Python 3.10 with PyTorch 2.1.0+cu121:
- `setuptools==69.5.1` (prevents `pkg_resources` removal in setuptools >= 70 from breaking `albumentations==0.4.3`)
- `numpy==1.24.4` (prevents NumPy 2.x ABI incompatibility with PyTorch 2.1)
- `Pillow==9.5.0` (prevents `font.getsize` removal in Pillow >= 10 from breaking `t3_dataset.py`)
- `pytorch-lightning==1.9.5` (retains `pytorch_lightning.utilities.distributed.rank_zero_only` removed in 2.x)
- `diffusers==0.10.2` & `huggingface-hub==0.25.2` (retains `cached_download` required by diffusers 0.10)
- `tokenizers==0.15.2` & `transformers==4.38.2`
- `opencv-python==4.7.0.72`
- `opencc==1.4.2`, `datasets>=2.14.0`, `modelscope>=1.23.0`

### 3. `scripts/setup_anytext2.sh`
Automates deployment deterministically:
- Non-interactive SSH conda path auto-discovery (`/mnt/data/zyx/miniconda3/bin`).
- Clones upstream AnyText2 and detaches at pinned commit `b06c583a583818f3679665ef67b51363f107853c`.
- Checks and idempotently applies `patches/anytext2/0001-anytext2-compatibility.patch` (`git apply --check` / `git apply -R --check`).
- Creates conda env `anytext2` from `environment.yaml` if not present.
- Verifies CUDA PyTorch 2.1.0+cu121 is active.
- Enforces `scripts/requirements-anytext2-compat.txt`.
- Downloads and verifies official ModelScope checkpoint `iic/cv_anytext2` (`anytext_v2.0.ckpt`).

### 4. `scripts/check_anytext2.sh` & `scripts/run_anytext2_demo.sh`
- Added non-interactive SSH conda auto-discovery.
- Added `--no-capture-output` to stream Python logs directly without unbuffered stalling.

---

## Verification Evidence

### Verification Approach
- **Patch Fresh Checkout Test**: Cloned a pristine AnyText2 repository at commit `b06c583a583818f3679665ef67b51363f107853c` into a temporary directory on `server-zyx`. Verified that `git apply --check` succeeds cleanly and `git apply -R --check` succeeds cleanly (idempotent).
- **Dependency Version Verification**: Verified all installed packages against `requirements-anytext2-compat.txt`.
- **Deployment Script Idempotency**: Executed `bash scripts/setup_anytext2.sh` on `server-zyx`; finished with exit code 0, recognized existing weights, and applied all checks.
- **Model Check**: Executed `bash scripts/check_anytext2.sh` on `server-zyx`:
  - `torch=2.1.0+cu121`, `cuda_available=True`
  - `gpu=NVIDIA GeForce RTX 4090`, `vram_gb=47.36`
  - Model weights loaded successfully, result `ANYTEXT2_SMOKE_TEST=PASS`.
- **Full Acceptance Smoke Test**: Executed `python scripts/smoke_test_anytext2.py` on `server-zyx`:
  - **Check 1 & 2**: Loaded AnyText2Model on GPU in 24.15s (FP16, translator disabled).
  - **Check 3 (Stock cartoon edit)**: Prompt `"a cartoon pig expression", "下班"`, generated in 14.57s, saved to `/mnt/data/zyx/SynSLP/outputs/smoke_test/stock_example_result.png`.
  - **Check 4 (SLP Chinese ship plate edit)**: Prompt `"a Chinese ship license plate", "皖宣城货0188"`, generated in 2.55s, saved to `/mnt/data/zyx/SynSLP/outputs/smoke_test/slp_reference_edit_result.png`.
  - **Verdict**: `STAGE 4 VERIFIED: ALL CHECKS PASSED (PASS)`. Peak VRAM: 12.52 GB.

---

## Deployment Metadata & Environment Specifications

- **Server Host**: `server-zyx` (`10.1.20.231`, Ubuntu 22.04 LTS)
- **GPU**: NVIDIA GeForce RTX 4090 (47.36 GB addressable)
- **Driver Version**: 580.119.02 | **CUDA**: 13.0
- **Python**: 3.10.6 (`/mnt/data/zyx/miniconda3/envs/anytext2/bin/python`)
- **PyTorch**: `2.1.0+cu121`
- **Torchvision**: `0.16.0+cu121`
- **Peak Inference VRAM**: 12.52 GB
- **AnyText2 Upstream Commit**: `b06c583a583818f3679665ef67b51363f107853c`
- **Model Weights**: ModelScope `iic/cv_anytext2` (`anytext_v2.0.ckpt`, 5.58 GB)

---

## Residual Limitations & Notes
1. **Hardware Requirement**: NVIDIA GPU with >= 16 GB VRAM is recommended for AnyText2 FP16 inference (12.52 GB peak VRAM observed during DDIM sampling).
2. **Legacy Package Compatibility**: Upstream AnyText2 code depends on older APIs (`pkg_resources`, `font.getsize`, PyTorch Lightning 1.x `rank_zero_only`). The tracked `scripts/requirements-anytext2-compat.txt` prevents newer incompatible package versions from breaking the environment.
