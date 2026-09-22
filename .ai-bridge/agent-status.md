# Agent Status: AnyText2 Baseline vs Font Mimic A/B Experiment

Updated: 2026-09-22T09:20:00.000Z
Status: COMPLETED (A/B REVIEW EVIDENCE READY)

## Overview
Successfully executed the controlled AnyText2 A/B experiment defined in `.ai-bridge/current-plan.md` on the representative tight-crop SLP (`东泰168` -> `苏航268`):
- **Question Tested**: Does AnyText2's native Font Mimic / font-hint conditioning materially improve style preservation when editing the text from `东泰168` to `苏航268`?
- **Condition A (Baseline)**: Native AnyText2 edit with `font_hint_image = [None] * 5`, `font_hint_mask = [None] * 5`.
- **Condition B (Font Mimic)**: Native AnyText2 edit with `font_hint_image` populated with reference image RGB and `font_hint_mask` populated with user mask.
- All other generation parameters (seed, steps, CFG scale, strength=1.0, prompts, resolution policy) strictly held identical between A and B.

---

## Fixed Inputs & Paths

- **Server**: `server-zyx` (`/mnt/data/zyx/SynSLP`)
- **Reference Image**: `/mnt/data/zyx/SynSLP/reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg` (`239 x 57`, 3-channel BGR uint8)
- **Mask Image**: `/mnt/data/zyx/SynSLP/mask/mask_easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.png` (`239 x 57`, binary `[0, 255]`, 87.79% editable)
- **Target Text**: `"苏航268"`

---

## Native Font Mimic API Semantics (Upstream AnyText2 Analysis)

Detailed findings from inspecting pinned upstream AnyText2 commit `b06c583a583818f3679665ef67b51363f107853c`:
1. **Parameter Definitions**:
   - `font_hint_image`: List of length 5 (or matching text line count). Slot 0 accepts a 3-channel RGB `numpy.ndarray` (`(H, W, 3)`, uint8, values 0-255).
   - `font_hint_mask`: List of length 5. Slot 0 accepts a single-channel `numpy.ndarray` (`(H, W)` or `(H, W, 1)`, uint8) where pixels > 0 indicate the source text/glyph region to mimic.
2. **Internal Processing**:
   - In `ms_wrapper.py:197-205`: When `font_hint_image[i]` is not None, `find_polygon` finds the contour of `font_hint_mask[i]`.
   - `draw_font_hint((font_hint_image[i]/127.5 - 1), poly)` extracts the localized font patch.
   - `crop_image` crops the oriented bounding box patch.
   - `ms_wrapper.py` sets `font_paths[i] = 'None'` so the external TTF font renderer is skipped for that line.
   - In `cldm/embedding_manager.py:253-264`: The cropped hint patch (`mimic_img`) is passed into the OCR/vision embedding branch as `style_line`, setting `style_flag = 1`.
3. **Format Preprocessing for Experiment**:
   - In-memory deterministic resolution scaling: Reference image scaled to `(512 x 128 x 3)` via Lanczos4 interpolation; user mask scaled to `(512 x 128 x 1)` via Nearest Neighbor interpolation.
   - No erosion, dilation, redrawing, or modification of the user's mask was performed.

---

## Fixed Generation Parameters

- **Hardware**: NVIDIA GeForce RTX 4090 on `server-zyx` (FP16, translator disabled)
- **Model Load Time**: 24.03s
- **Seed**: `2026`
- **Strength**: `1.0`
- **DDIM Steps**: `20`
- **CFG Scale**: `9.0`
- **Eta**: `0.0`
- **Mode**: `"edit"`
- **Sort Priority**: `"↔"`
- **Revise Position**: `False`
- **Attention Scale (attnx_scale)**: `1.0`
- **Font Hollow**: `False`
- **Prompt (img_prompt)**: `"a Chinese ship license plate"`
- **Positive Prompt (a_prompt)**: `"a Chinese ship license plate, white text, realistic photo"`
- **Negative Prompt (n_prompt)**: `"low quality, blurry, noisy"`

---

## A/B Experimental Results

Output Directory:
`/mnt/data/zyx/SynSLP/outputs/font_mimic_ab/dongtai168/`

| Condition | Inference Time | Diffusion Output (512x128) | Scaled-Back Output (239x57) |
| :--- | :---: | :--- | :--- |
| **A. Baseline** (Mimic Disabled) | 2.74s | `baseline.png` | `baseline_orig_res.png` |
| **B. Font Mimic** (Mimic Enabled) | 2.20s | `font_mimic.png` | `font_mimic_orig_res.png` |

### Side-by-Side Comparison Grid
- **Full Resolution (512x488)**: [`outputs/font_mimic_ab/dongtai168/comparison.png`](file:///home/kyrie/cxprojects/SynSLP/outputs/font_mimic_ab/dongtai168/comparison.png)
- **Original Resolution (239x275)**: [`outputs/font_mimic_ab/dongtai168/comparison_orig_res.png`](file:///home/kyrie/cxprojects/SynSLP/outputs/font_mimic_ab/dongtai168/comparison_orig_res.png)

---

## Human Review Evaluation Prompts

Per the plan, no auto-scoring is applied. The visual evidence is ready for evaluation against the four criteria:
1. **Text Consistency**: Is the generated text visually consistent with `苏航268`?
2. **Style Preservation**: Does Font Mimic preserve the original `东泰168` glyph/font/paint style better than Baseline?
3. **Redraw Tendency**: Does Font Mimic reduce unnecessary regeneration of the SLP's original visual appearance (e.g. the right-side framed box vs single plate)?
4. **Naturalness**: Are the Chinese characters and digits more natural and coherent?

---

## Files Changed & Git Consistency

- Added entry point: `scripts/run_font_mimic_ab.py`
- Updated status & logs: `.ai-bridge/agent-status.md`, `.ai-bridge/execution-log.jsonl`
- Git commit: clean synchronization across Local, GitHub origin/main, and `server-zyx`.
