# Agent Status: SynSLP AnyText2 Deployment & Multi-End Sync

Updated: 2026-09-22T06:01:00.000Z
Status: COMPLETED (ALL STAGES VERIFIED PASS)

## Overview
Successfully executed all 4 stages defined in `.ai-bridge/current-plan.md` using the RGSLPR-compatible SSH approach (`ssh -o ClearAllForwardings=yes server-zyx`):
1. Established local ↔ GitHub Git baseline.
2. Synchronized GitHub → server-zyx (`/mnt/data/zyx/SynSLP`).
3. Deployed official AnyText2 on server-zyx with an isolated Conda environment and official ModelScope weights.
4. Performed minimal deployment acceptance test including both official stock edit and real Chinese ship-license-plate (SLP) edit.

---

## Stage Verification Summary

### Stage 1: Local ↔ GitHub Git Baseline
- **Local Root**: `/home/kyrie/cxprojects/SynSLP`
- **GitHub**: `kyrie21z/SynSLP` (branch `main`)
- **Actions**:
  - Initialized local git repository, added remote origin.
  - Safely merged upstream commits (`7413a06`) with local additions (`.agents/skills/`, `skills-lock.json`, `.ai-bridge/`).
  - Pushed to `origin/main` without force-pushing.
- **Verdict**: **PASS** (`local HEAD == origin/main`, working tree clean).

### Stage 2: Sync GitHub → server-zyx
- **Target**: `server-zyx:/mnt/data/zyx/SynSLP`
- **Actions**:
  - Cloned repository directly on `server-zyx` from `git@github.com:kyrie21z/SynSLP.git`.
  - Verified remote references and branch alignment.
- **Verdict**: **PASS** (`local HEAD == origin/main == server HEAD == d5836a0`, working tree clean).

### Stage 3: Deploy Official AnyText2 on server-zyx
- **Upstream Source**: `https://github.com/tyxsspa/AnyText2.git`
- **Pinned Commit**: `b06c583a583818f3679665ef67b51363f107853c` (at `third_party/AnyText2`, excluded from Git).
- **Conda Environment**: `anytext2` located at `/mnt/data/zyx/miniconda3/envs/anytext2`.
- **Checkpoint**: ModelScope `iic/cv_anytext2` (5.58 GB `anytext_v2.0.ckpt` + CLIP large patch 14 weights).
- **Verdict**: **PASS** (`models/anytext_v2.0.ckpt` ready, `check_anytext2.sh` passed).

### Stage 4: Minimal Deployment Acceptance Test
- **Test Script**: `scripts/smoke_test_anytext2.py`
- **Check 1 & 2 (Load Model & CUDA Initialization)**:
  - AnyText2Model initialized on GPU in 23.87s with FP16 and translator disabled (`PASS`).
- **Check 3 (Stock Example Inference)**:
  - Input: `example_images/ref2.jpg` + mask `example_images/edit2.png`, prompt `"a cartoon pig expression"`, text `'"下班"'`.
  - Result: Generated in 12.94s, output saved to `/mnt/data/zyx/SynSLP/outputs/smoke_test/stock_example_result.png` (`PASS`).
- **Check 4 (Chinese Ship License Plate Reference Edit)**:
  - Input: Real ship license plate image from `/mnt/data/zyx/SLP34K/ocr_training/data/pairs/target_2_High_quality_categorized/7755/O_20190510_13_26_50_516000.jpg&&&&7755&&&&5-浙绍兴货0668.jpg`.
  - Target Text: `"皖宣城货0188"`.
  - Prompt: `"a Chinese ship license plate, blue background, white clean text, realistic photo"`.
  - Result: Generated in 2.46s, output saved to `/mnt/data/zyx/SynSLP/outputs/smoke_test/slp_reference_edit_result.png` (`PASS`).
- **Verdict**: **PASS** (reproducibly verified).

---

## Deployment Metadata & Environment Specifications

- **Server Host**: `server-zyx` (`10.1.20.231`, Ubuntu 22.04 LTS)
- **GPU**: NVIDIA GeForce RTX 4090 (24GB physical / 48GB configured, 47.36 GB addressable)
- **Driver Version**: 580.119.02 | **System CUDA**: 13.0
- **Python**: 3.10.6 (`/mnt/data/zyx/miniconda3/envs/anytext2/bin/python`)
- **PyTorch**: `2.1.0+cu121`
- **Torchvision**: `0.16.0+cu121`
- **Peak Inference VRAM**: 12.52 GB
- **AnyText2 Upstream Commit**: `b06c583a583818f3679665ef67b51363f107853c`
- **Checkpoint**: ModelScope `iic/cv_anytext2` (`anytext_v2.0.ckpt`, SHA256 verified)
- **Execution Command**:
  ```bash
  export PATH="/mnt/data/zyx/miniconda3/bin:$PATH"
  cd /mnt/data/zyx/SynSLP
  python scripts/smoke_test_anytext2.py
  ```

---

## Encountered Errors & Minimal Compatibility Fixes

1. **Non-interactive SSH Conda PATH**:
   - *Issue*: Non-login SSH does not load `/mnt/data/zyx/miniconda3/bin` into `PATH`.
   - *Fix*: Explicitly exported `PATH="/mnt/data/zyx/miniconda3/bin:$PATH"` before executing scripts.
2. **Albumentations / Setuptools 83+ `pkg_resources` Removal**:
   - *Issue*: Modern setuptools >= 70 removed `pkg_resources`, breaking `albumentations==0.4.3` install.
   - *Fix*: Pinned `setuptools<70` (`69.5.1`) inside the `anytext2` environment.
3. **NumPy 2.x ABI Incompatibility with PyTorch 2.1**:
   - *Issue*: Pip pulled `numpy 2.2.6`, causing `Failed to initialize NumPy: _ARRAY_API not found` in PyTorch 2.1.
   - *Fix*: Pinned `numpy==1.24.4`.
4. **PyTorch Lightning 2.x API Change**:
   - *Issue*: Upstream `AnyText2` imports `from pytorch_lightning.utilities.distributed import rank_zero_only`, which was removed in PyTorch Lightning 2.0+.
   - *Fix*: Installed `pytorch-lightning<2.0` (`1.9.5`).
5. **Pillow >= 10 `font.getsize` Removal**:
   - *Issue*: `t3_dataset.py` calls `new_font.getsize(text)`, which was removed in Pillow >= 10.
   - *Fix*: Pinned `Pillow==9.5.0` as specified in upstream `environment.yaml`.
6. **Vanilla CrossAttention FP16 Half/Float Type Mismatch**:
   - *Issue*: Without `xformers`, fallback attention calculates float32 `sim` and float16 `v`, triggering `RuntimeError: expected scalar type Half but found Float` in `einsum`.
   - *Fix*: Added `.to(v.dtype)` to `sim = sim.softmax(dim=-1).to(v.dtype)` in `ldm/modules/attention.py:190`.
7. **`sort_priority` Unicode Arrow Expectation**:
   - *Issue*: `ms_wrapper.py:separate_pos_imgs` expects `sort_priority` to be `'↕'` or `'↔'`.
   - *Fix*: Updated `scripts/smoke_test_anytext2.py` to pass `'↔'`, and added defensive fallback `fir, sec = 0, 1` in `ms_wrapper.py:370`.
