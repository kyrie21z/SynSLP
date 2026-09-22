# Agent Status: AnyText2 Single-Image SLP Edit Strength Tuning

Updated: 2026-09-22T08:38:00.000Z
Status: COMPLETED (REVIEW EVIDENCE READY)

## Overview
Successfully executed all requirements in `.ai-bridge/current-plan.md` for single-image edit strength tuning on a representative tight-crop SLP:
- Target SLP: `东泰168` -> `苏航268`
- Isolated variable: Edit strength (`0.3`, `0.5`, `0.7`, `1.0`)
- All other generation parameters (seed, prompt, negative prompt, steps, CFG scale, sort priority, resolution policy) strictly held identical across all 4 runs.
- Generated individual outputs at both diffusion resolution (512x128) and original resolution (239x57).
- Created a labeled vertical comparison grid for direct visual review.

---

## Fixed Inputs & Validation

- **Reference Image**: `/mnt/data/zyx/SynSLP/reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg`
  - Dimensions: `239 x 57` (width=239, height=57, channels=3, uint8)
- **Mask Image**: `/mnt/data/zyx/SynSLP/mask/mask_easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.png`
  - Dimensions: `239 x 57` (exact match with reference)
  - Values: Binary `[0, 255]`
  - Editable Text Area: `11960 / 13623` pixels (`87.79%`, value 255)
- **Target Text**: `"苏航268"`

---

## Resolution Policy & Technical Note

AnyText2's internal pipeline (`ms_wrapper.py` & `util.py:resize_image`) strictly requires spatial dimensions to be multiples of 64 (`new_dim = dim - (dim % 64)`). Because original height `57 < 64`, unadapted dimensions calculate target height to 0 and trigger OpenCV resize assertion failures.
Per user clarification, an in-memory deterministic resolution policy was applied:
- In-memory scaling: `(239 x 57)` -> `(512 x 128)` for diffusion sampling (aspect ratio 4.00 vs 4.19 original).
- High-resolution diffusion output saved directly (`512 x 128`).
- Lanczos4 scaled-back output saved at exact original resolution (`239 x 57`).

---

## Fixed Generation Parameters

- **Hardware**: NVIDIA GeForce RTX 4090 on `server-zyx` (FP16 mode, translator disabled)
- **Model Load Time**: 23.40s
- **Seed**: `2026`
- **DDIM Steps**: `20`
- **CFG Scale**: `9.0`
- **Eta**: `0.0`
- **Mode**: `"edit"`
- **Sort Priority**: `"↔"`
- **Prompt (img_prompt)**: `"a Chinese ship license plate"`
- **Positive Prompt (a_prompt)**: `"a Chinese ship license plate, blue background, white clean text, realistic photo"`
- **Negative Prompt (n_prompt)**: `"low quality, blurry, noisy"`

---

## Experimental Results & Output Paths

Directory on `server-zyx` (and local mirror):
`/mnt/data/zyx/SynSLP/outputs/single_image_tuning/dongtai168/`

| Strength | Inference Time | Diffusion Output (512x128) | Scaled-Back Output (239x57) | Notes / Visual Observations |
| :---: | :---: | :--- | :--- | :--- |
| **0.3** | 2.77s | `strength_0.3.png` | `strength_0.3_orig_res.png` | Insufficient control; text area shows distorted noisy strokes; target text not formed. |
| **0.5** | 2.13s | `strength_0.5.png` | `strength_0.5_orig_res.png` | Control remains weak; character strokes partially form but digits/characters are heavily fragmented. |
| **0.7** | 2.17s | `strength_0.7.png` | `strength_0.7_orig_res.png` | "苏" and "航" appear distinctly; digit region partially forms ("2 1 8" variant). |
| **1.0** | 2.28s | `strength_1.0.png` | `strength_1.0_orig_res.png` | High text fidelity; "苏" and "航" glyphs are clear, digits formed ("E 6 5" / modified digit styles); background SLP texture preserved. |

### Side-by-Side Comparison Grids
- **High-Resolution Grid (512x820)**: `/mnt/data/zyx/SynSLP/outputs/single_image_tuning/dongtai168/comparison_grid.png`
- **Original-Resolution Grid (239x465)**: `/mnt/data/zyx/SynSLP/outputs/single_image_tuning/dongtai168/comparison_grid_orig_res.png`

---

## Git Consistency

- **Commit**: `b189db6be5b0734a02371865d1967e0981275c9b`
- **Local HEAD == origin/main == server HEAD**: All verified aligned.
- **Tracked Entry Point**: `scripts/tune_anytext2_strength.py`
- **Working Tree**: Clean on both local and `server-zyx`.
