# Run single-glyph Font Mimic ablation

Updated: 2026-09-22T15:21:15.308Z
Workspace: /home/kyrie/cxprojects/SynSLP
Target agent: Codex (codex)

## Plan

# Goal

Run exactly one controlled AnyText2 **Font Mimic ablation** on the current best single-character edit formulation:

[
	ext{东泰168} ightarrow 	ext{东泰268}
]

The current painted-hull prompt has already removed the major physical-license-plate/rectangular-carrier prior. The remaining visible failure is primarily **glyph/style mismatch**: the generated `2` is recognizable and locally blended, but its stroke width, paint texture, and glyph appearance do not match the original `1/6/8` style.

This task tests one hypothesis only:

> Can AnyText2 native Font Mimic make the generated `2` visually closer to the original SLP glyph style when the source hint is the single original glyph `1`?

Only one experimental variable may change:

[
	ext{Font Mimic OFF} ightarrow 	ext{Font Mimic ON}
]

Everything else must remain identical to the completed painted-hull prompt run.

# Frozen baseline

Use the completed painted-hull run as condition A.

Baseline output directory:

`outputs/prompt_ablation/dongtai168_order2_hull_prompt/`

Baseline task:

- reference image: `东泰168`
- source instance: `order=2`
- source glyph: `1`
- source bbox: `[120, 3, 147, 52]`
- replacement text: `"2"`
- expected full visual text: `东泰268`
- edit mask: exact order-2 bbox mask
- original mask active pixels: `1323`
- original image size: `239x57`
- 512x512 aspect-ratio-preserving black letterbox
- letterbox scale: `512/239 ≈ 2.142259`
- padding: `pad_x=0`, `pad_y=195`
- target text prompt: `"2"`
- seed: `2026`
- DDIM steps: `20`
- strength: `1.0`
- CFG: `7.5`
- eta: `0.0`
- sort priority: `↔`
- `revise_pos=False`
- `attnx_scale=1.0`
- image count: `1`
- checkpoint/environment: unchanged verified AnyText2 deployment
- `show_debug`: keep the exact value used by baseline
- output compositing / inverse letterbox: unchanged

Frozen `img_prompt`:

```text
a close-up photo of white painted Chinese characters and digits directly on a dark weathered metal ship hull, worn paint, realistic surface texture
```

Frozen `a_prompt`:

```text
best quality, extremely detailed,4k, HD, supper legible text,  clear text edges,  clear strokes, neat writing, no watermarks
```

Frozen `n_prompt`:

```text
low-res, bad anatomy, extra digit, fewer digits, cropped, worst quality, low quality, watermark, unreadable text, messy words, distorted text, disorganized writing, advertising picture
```

Condition A:

```text
Font Mimic = OFF
font_hint_image = [None] * 5
font_hint_mask  = [None] * 5
```

Do not rerun condition A if its metadata proves all frozen parameters above; reuse the existing saved A output. If comparability cannot be proven, stop and report rather than silently rerunning with changed conditions.

# Step 1 — Verify native single-glyph Font Mimic input

Before inference, inspect the pinned AnyText2 runtime path already deployed and confirm the exact input requirements for `font_hint_image` and `font_hint_mask`.

Use the existing verified native Font Mimic path; do not modify third-party AnyText2 code.

Condition B must use:

- `font_hint_image`: the **original reference image**, transformed using the exact same 512x512 letterbox geometry as the edit input;
- `font_hint_mask`: the **same order-2 glyph bbox region** corresponding to source glyph `1`, transformed with the exact same letterbox geometry;
- one active font-hint slot corresponding to the single target text entry;
- all unused font-hint slots set exactly as required by native AnyText2.

The source style hint is therefore:

[
1 	ext{source glyph} ightarrow 1 	ext{target glyph }2
]

This is intentional: source and target have equal character count.

Do not create a new hand-drawn font mask, glyph segmentation mask, dilation, erosion, feathering, or padding in this task. The purpose is to isolate the effect of native Font Mimic only.

Record the exact shape, dtype, channel order, and slot used for the font hint.

# Step 2 — Run exactly one Font Mimic ON inference

Run one fresh inference on `server-zyx`.

Condition B differs from A only in:

```text
Font Mimic = ON
font_hint_image[active_slot] = original reference letterbox
font_hint_mask[active_slot]  = order-2 source-glyph region
```

All other variables must be byte/config-equivalent to the painted-hull baseline where applicable.

Do not change:

- `img_prompt`;
- `a_prompt`;
- `n_prompt`;
- edit mask;
- bbox;
- letterbox geometry;
- seed;
- CFG;
- DDIM steps;
- strength;
- eta;
- target text;
- model/checkpoint;
- precision;
- output compositing;
- any preprocessing unrelated to the font-hint path.

Generate exactly one sample.

# Step 3 — Save minimal A/B evidence

Use a dedicated directory such as:

`outputs/font_mimic_single_char/dongtai168_order2_1_to_2/`

Required artifacts:

- `font_mimic_output_512.png`
- `font_mimic_output_crop_original_res.png`
- `comparison_font_mimic_ab.png`
- `metadata.json`

The comparison must contain at minimum:

1. original reference `东泰168`;
2. condition A: painted-hull prompt + Font Mimic OFF;
3. condition B: painted-hull prompt + Font Mimic ON;
4. zoomed detail of source glyph `1`, A-generated `2`, and B-generated `2`.

Do not enhance, sharpen, recolor, feather, or otherwise post-process either generated result.

Record:

- baseline metadata path/hash if available;
- exact source order/text/bbox;
- exact Font Mimic image/mask preprocessing;
- active font-hint slot;
- exact effective generation parameters;
- inference time;
- warnings/errors;
- output paths.

# Human review criteria

Do not auto-score and do not declare the experiment successful.

Human review will judge only:

1. Is target glyph `2` still clearly recognizable?
2. Does Font Mimic make its stroke width closer to source `1` and neighboring `6/8`?
3. Does its white-paint texture / weathering better match the original glyphs?
4. Are glyph edge characteristics closer to the source style?
5. Does Font Mimic preserve the improved hull/background continuity from the painted-hull prompt?
6. Does it introduce any new artifact, deformation, carrier patch, or loss of legibility?

# Decision boundary

After this one B run:

- if Font Mimic clearly improves glyph/style consistency without degrading background continuity or legibility, retain Font Mimic for subsequent single-character experiments;
- if Font Mimic gives negligible improvement or worsens the glyph, treat native Font Mimic as insufficient for this SLP case and do **not** sweep Font Mimic parameters; next investigate edit-mask geometry / glyph-shaped masks;
- if Font Mimic changes background/carrier behavior unexpectedly, inspect the native font-hint crop/debug evidence before changing any other parameter.

# Stop condition

Stop immediately after the one Font Mimic ON output and the A/B review board are produced.

Out of scope:

- generating additional seeds;
- Font Mimic strength/tuning sweeps;
- alternative font-hint source glyphs;
- using `6` or `8` as source hints;
- multi-glyph font hints;
- glyph-shaped edit masks;
- mask dilation/erosion/feathering;
- prompt tuning;
- CFG/strength/DDIM sweeps;
- editing `泰 -> 航`;
- multi-character edits;
- OCR scoring/filtering;
- batch synthesis;
- downstream training.

# Implementation contract

- Change exactly one experimental factor: native Font Mimic OFF -> ON.
- Reuse the existing painted-hull single-character pipeline.
- Keep human annotations unchanged.
- Keep third-party AnyText2 architecture/source unchanged.
- Do not overwrite the existing painted-hull baseline artifacts.
- Update `.ai-bridge/agent-status.md` with exact inputs, frozen-parameter proof, Font Mimic preprocessing, outputs, and blockers.
- Save the final review diff to `.ai-bridge/implementation-diff.patch` when practical.
- Append notable execution events to `.ai-bridge/execution-log.jsonl` when supported.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
