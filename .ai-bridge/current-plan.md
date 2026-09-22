# Run single-variable prompt ablation

Updated: 2026-09-22T14:56:31.760Z
Workspace: /home/kyrie/cxprojects/SynSLP
Target agent: Codex (codex)

## Plan

# Goal

Run exactly one controlled AnyText2 prompt-ablation on the already validated single-character edit:

[
	ext{东泰168} ightarrow 	ext{东泰268}
]

The purpose is to test one hypothesis only:

> Is the visible rectangular/plate-like patch around the generated digit mainly caused by the current image prompt `"a realistic photo of a Chinese ship license plate"` activating an inappropriate physical-license-plate prior?

Only `img_prompt` may change. Everything else must remain identical to the previous single-character run.

# Frozen baseline evidence

Previous accepted run:

- reference: `东泰168`
- selected instance: `order=2`
- source glyph: `1`
- bbox: `[120, 3, 147, 52]`
- replacement text: `2`
- expected full text: `东泰268`
- original mask active pixels: `1323`
- original image size: `239x57`
- letterbox: aspect-ratio-preserving black `512x512`
- scale: `512/239 ≈ 2.142259`
- padding: `pad_x=0`, `pad_y=195`
- Font Mimic: disabled
- seed: `2026`
- DDIM steps: `20`
- strength: `1.0`
- eta: `0.0`
- sort priority: `↔`
- `revise_pos=False`
- `attnx_scale=1.0`
- CFG: `7.5`
- official text-quality `a_prompt` and `n_prompt` from the prior run
- one output image only

Previous image prompt:

```text
a realistic photo of a Chinese ship license plate
```

Previous result interpretation:

- target glyph replacement: PASS;
- outside-mask preservation: PASS;
- edit-region appearance/style continuity: FAIL/weak;
- visible rectangular patch around generated `2`.

Do not reuse the previous Agent claim that the visual result was fully successful. This task treats the rectangular patch as a real failure mode to diagnose.

# Step 1 — Verify single-variable comparability

Before inference, read the previous run metadata/artifacts and confirm that all frozen parameters above match the current execution path.

Use the existing human annotation and order-based mask path unchanged.

Do not:
- redraw or alter the bbox;
- change mask padding;
- change letterbox geometry;
- enable Font Mimic;
- change seed;
- change CFG;
- change DDIM steps;
- change strength;
- change `a_prompt`;
- change `n_prompt`;
- change target text;
- change model/checkpoint;
- change output compositing logic.

If any baseline parameter cannot be reproduced exactly, stop and report the mismatch rather than continuing.

# Step 2 — Change only img_prompt

Replace only:

```text
a realistic photo of a Chinese ship license plate
```

with exactly:

```text
a close-up photo of white painted Chinese characters and digits directly on a dark weathered metal ship hull, worn paint, realistic surface texture
```

Rationale:
- describe the actual visual substrate rather than the task/category;
- explicitly state that the text is painted directly on metal;
- avoid words such as `license plate`, `sign`, `plaque`, `board`, or `frame` that may encourage a separate rectangular carrier.

Do not tune or paraphrase this prompt during the run.

# Step 3 — Run exactly one new inference

Run one fresh AnyText2 inference on `server-zyx` using the exact same:

- reference image;
- `order=2` mask;
- 512x512 black letterbox;
- target text `"2"`;
- checkpoint/environment;
- all frozen parameters from the baseline.

Font Mimic remains disabled.

If `show_debug=True` was enabled in the previous run, keep it enabled; otherwise keep the previous value. Do not change debug behavior as another variable.

# Step 4 — Save minimal A/B review evidence

Use a dedicated output directory, for example:

`outputs/prompt_ablation/dongtai168_order2_hull_prompt/`

Required artifacts:

- `output_512.png`
- `output_crop_original_res.png`
- `comparison_prompt_ab.png`
- `metadata.json`

The comparison should contain:

1. original reference `东泰168`;
2. previous baseline output using `license plate` prompt;
3. new output using the `painted ... ship hull` prompt.

Do not add enhancement/post-processing.

Record in metadata/status:

- old `img_prompt`;
- new `img_prompt`;
- proof that all other parameters were identical;
- inference time;
- output paths;
- warnings/errors.

# Human review criteria

Do not auto-score or declare a winner.

Human review will judge only:

1. Does `1 -> 2` remain recognizable?
2. Is the rectangular/plate-like patch around `2` reduced?
3. Does the generated region better match the surrounding dark weathered hull texture?
4. Are `东泰`, `6`, and `8` still preserved?
5. Does the new result look more like painted text on the same hull rather than a pasted/re-generated rectangular object?

# Decision boundary

After this single run:

- if the rectangular patch is substantially reduced, treat prompt prior as an important cause and continue with prompt formulation before changing mask geometry;
- if the rectangular patch remains essentially unchanged, treat destructive rectangular bbox masking/background regeneration as the more likely primary cause, and move next to a tighter foreground/glyph-shaped edit mask rather than doing a prompt sweep.

# Stop condition

Stop immediately after this one prompt-ablation output and A/B comparison are produced.

Out of scope:

- any additional prompt variants;
- CFG sweep;
- strength sweep;
- seed sweep;
- DDIM sweep;
- Font Mimic;
- mask dilation/erosion;
- glyph segmentation implementation;
- editing `泰 -> 航`;
- multi-character edits;
- OCR scoring/filtering;
- batch synthesis;
- downstream training.

# Implementation contract

- Change exactly one experimental variable: `img_prompt`.
- Reuse existing single-character edit code; do not create a new pipeline unless a tiny flag/argument is needed.
- Keep human annotations unchanged.
- Do not modify third-party AnyText2 architecture.
- Update `.ai-bridge/agent-status.md` with exact parameters, evidence, outputs, and blockers.
- Save the final diff to `.ai-bridge/implementation-diff.patch` when practical.
- Append notable execution events to `.ai-bridge/execution-log.jsonl` when supported.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
