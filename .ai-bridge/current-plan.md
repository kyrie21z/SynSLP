# Compare AnyText2 baseline vs Font Mimic

Updated: 2026-09-22T09:15:52.223Z
Workspace: /home/kyrie/cxprojects/SynSLP
Target agent: Codex (codex)

## Plan

# Goal

Run exactly one controlled AnyText2 A/B experiment on the representative tight-crop SLP `东泰168` to answer one question:

> Does AnyText2's native Font Mimic / font-hint conditioning materially improve style preservation when editing the text from `东泰168` to `苏航268`?

This is NOT a strength sweep and NOT a synthetic-data pipeline task.

The previous strength experiment is complete. Its key engineering finding is that the current `strength` parameter is a Control/WriteNet conditioning scale, not an img2img denoising-strength control. Therefore do not sweep or reinterpret `strength` again. Fix it at `1.0`.

The current manually supplied edit mask covers about 87.79% of the tight SLP crop. Standard AnyText2 edit therefore has very little unmasked SLP content available as a preservation anchor inside the crop. The purpose of this experiment is only to test whether the model's existing native font/style hint path can recover useful reference style under this exact setup.

## Fixed inputs

Server:
- host: `server-zyx`
- repo: `/mnt/data/zyx/SynSLP`

Reference image:
- `/mnt/data/zyx/SynSLP/reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg`

User-provided mask:
- `/mnt/data/zyx/SynSLP/mask/mask_easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.png`

Target text:
- exactly `苏航268`

Generator:
- existing verified AnyText2 deployment
- keep the currently pinned AnyText2 revision, checkpoint, FP16 environment, compatibility patch, and translator-disabled configuration unchanged

Fixed generation parameters:
- mode: `edit`
- seed: `2026`
- strength: `1.0`
- DDIM steps: `20`
- CFG scale: `9.0`
- eta: `0.0`
- sort priority: `↔`
- revise_pos: `False`
- attnx_scale: `1.0`
- font_hollow: `False`
- img_prompt: current `a Chinese ship license plate`
- a_prompt: current neutral prompt `a Chinese ship license plate, white text, realistic photo`
- n_prompt: current `low quality, blurry, noisy`
- text_colors: leave unchanged from the working path
- resolution policy: use the same deterministic `239x57 -> 512x128` in-memory scaling already verified by the strength-tuning script, with the same interpolation choices

Do not change any of these between A and B.

## Step 1 — Verify the exact native Font Mimic interface

Before implementing the comparison, inspect only the pinned AnyText2 code actually used by the working deployment and determine the exact runtime semantics of:
- `font_hint_image`
- `font_hint_mask`
- their list length / per-text-line indexing
- accepted image/mask shape, dtype, value range, color order, and resolution
- whether the hint mask is interpreted as text/reference region and how it is resized internally

Do not guess these details and do not redesign AnyText2.

Record the relevant upstream file/function names and the conclusion in `.ai-bridge/agent-status.md`.

Hard constraint:
- Use the user's existing reference image as the source of the font/style hint.
- Use the user's existing mask as the source of the font-hint region if it is compatible with the native API.
- If the native API requires only deterministic format adaptation (resize, channel conversion, dtype/range conversion), do that in memory and record it.
- Do NOT manually redraw, shrink, expand, erode, dilate, blur, or otherwise invent a new mask.
- If the supplied mask is fundamentally incompatible with Font Mimic semantics, stop and report that exact incompatibility instead of silently substituting another mask.

## Step 2 — Implement the smallest A/B entry point

Prefer minimally modifying or reusing the existing single-image tuning code. Do not create a general pipeline or new package architecture.

Run two conditions from the same model load and with identical fixed inputs/parameters:

### A. Baseline
Native AnyText2 edit with Font Mimic disabled:
- `font_hint_image = [None] * 5`
- `font_hint_mask = [None] * 5`

### B. Font Mimic
Native AnyText2 edit with Font Mimic enabled for the single target text entry:
- populate the correct first/active font-hint slot using the reference image
- populate the corresponding font-hint mask slot using the user mask
- leave unused slots exactly as required by the native API

Do not alter `glyline_font_path`, prompt wording, target text, seed, edit mask, strength, resolution, or any other parameter merely to make B look better.

Both A and B must be generated fresh under the same current code/config; do not use an old strength-sweep image as the baseline unless you first prove it is produced with byte-identical effective parameters. Fresh A/B generation is preferred.

## Step 3 — Run exactly the two conditions

Write outputs under a dedicated directory, for example:

`/mnt/data/zyx/SynSLP/outputs/font_mimic_ab/dongtai168/`

Required artifacts:
- `reference.png` or an exact review copy of the reference
- `mask.png` or an exact review copy of the mask
- `baseline.png` — diffusion-resolution A output
- `font_mimic.png` — diffusion-resolution B output
- `baseline_orig_res.png` — A scaled back to 239x57
- `font_mimic_orig_res.png` — B scaled back to 239x57
- `comparison.png` — labeled visual comparison containing at minimum:
  1. Reference: 东泰168
  2. Baseline: 苏航268
  3. Font Mimic: 苏航268

Keep the comparison rendering itself lossless and do not apply enhancement or post-processing.

Record inference time and warnings/errors for both conditions.

## Step 4 — Produce review evidence and stop

Update `.ai-bridge/agent-status.md` with:
- exact reference and mask paths
- target text
- exact fixed generation parameters
- exact Font Mimic API semantics found in pinned upstream code
- exact preprocessing applied to reference/mask for the font-hint path
- A and B output paths
- inference time for A and B
- any warnings/errors
- files changed and verification performed

Do NOT auto-score, OCR-filter, or declare a winner.

The human review will judge only:
1. Is the generated text actually visually consistent with `苏航268`?
2. Does Font Mimic preserve the original `东泰168` glyph/font/paint style better than Baseline?
3. Does it reduce unnecessary regeneration of the SLP's original visual appearance?
4. Are the Chinese characters and digits more natural and coherent?

## Decision boundary

This experiment must not make the downstream decision automatically, but its purpose is to supply evidence for this binary choice:

- If Font Mimic gives a clear qualitative improvement, continue refining the AnyText2 SLP editing formulation.
- If Font Mimic still substantially redraws the whole tight-crop plate or fails to preserve useful style, treat that as evidence that standard AnyText2 editing is poorly matched to this tight-crop SLP use case; stop brute-force parameter tuning before considering another reference-preserving editing approach.

## Stop condition

Stop immediately after the two fresh outputs and the review comparison/evidence are produced.

Out of scope:
- any additional strength values
- seed sweep
- prompt sweep
- mask redesign
- new reference images
- new target strings
- multiple samples
- OCR verification/filtering
- automatic image-quality metrics
- batch generation
- manifest generation
- synthetic-data pipeline
- Qwen comparison
- model training/fine-tuning
- AnyText2 architecture modification
- downstream SLPR training

## Implementation contract

- Keep edits minimal and reviewable.
- Treat the pinned AnyText2 implementation as the source of truth for Font Mimic semantics.
- Do not modify third-party AnyText2 architecture to force this experiment to work.
- Run only focused verification required for this A/B.
- Update `.ai-bridge/agent-status.md` with the final evidence.
- Save the final review diff to `.ai-bridge/implementation-diff.patch` when practical.
- Append notable execution events to `.ai-bridge/execution-log.jsonl` when supported.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
