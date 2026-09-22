# Tune one AnyText2 SLP edit

Updated: 2026-09-22T08:31:41.548Z
Workspace: /home/kyrie/cxprojects/SynSLP
Target agent: Codex (codex)

## Plan

# Goal

Find a usable AnyText2 edit configuration for exactly one representative tight-crop SLP by isolating a single variable: edit strength.

Do not design a batch synthesis pipeline. Do not change reference image, mask, target text, seed, prompt, DDIM steps, CFG, model revision, or any other generation parameter across the comparison.

## Fixed inputs

Server:
- host: server-zyx
- repo: /mnt/data/zyx/SynSLP

Reference:
- /mnt/data/zyx/SynSLP/reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg

Mask:
- /mnt/data/zyx/SynSLP/mask/mask_easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.png

Target text:
- 苏航268

Generator:
- existing verified AnyText2 deployment
- keep the currently pinned AnyText2 revision and working FP16 environment unchanged

## 1. Validate the two fixed inputs before inference

On server:
- confirm both files exist and are readable;
- record reference width/height;
- record mask width/height and verify it matches the reference exactly;
- verify the mask is effectively binary and determine which value is treated by the current AnyText2 path as editable;
- do not redraw, resize, blur, dilate, erode, or otherwise alter the user's mask unless the existing AnyText2 API itself requires a deterministic format conversion;
- if conversion to 3-channel/binary uint8 is required, do only that in memory and record it.

Stop if dimensions or mask semantics are invalid rather than silently repairing them.

## 2. Create the smallest single-image tuning entry point

Reuse the already verified AnyText2 loading/inference path rather than creating a new abstraction layer.

Implement only what is necessary to run the fixed reference + fixed mask + fixed target repeatedly with a configurable strength.

Requirements:
- reference and mask paths are explicit CLI/config inputs or fixed in a dedicated tuning script;
- target text is exactly 苏航268;
- mode remains edit;
- keep the same seed for all runs;
- keep identical prompt, negative prompt, DDIM steps, CFG, sort priority, resolution policy, and all other parameters for all runs;
- do not introduce OCR filtering, manifest generation, sampling logic, multiprocessing, or batch infrastructure.

Before running, inspect the current AnyText2 wrapper to ensure the external mask is passed with the correct polarity/shape and that the `strength` argument used here is the actual edit-strength control in the working inference path.

## 3. Run exactly four strength values

Generate one output for each:

- strength = 0.3
- strength = 0.5
- strength = 0.7
- strength = 1.0

All non-strength variables must be byte-for-byte/config-identical across the four runs where applicable.

Use one deterministic seed for all four outputs.

Write outputs under a dedicated directory such as:

/mnt/data/zyx/SynSLP/outputs/single_image_tuning/dongtai168/

Use unambiguous filenames, e.g.:
- strength_0.3.png
- strength_0.5.png
- strength_0.7.png
- strength_1.0.png

Also save/copy the exact reference and mask used into that experiment directory only if needed for human review; do not modify the originals.

## 4. Produce review evidence, then stop

Record:
- exact reference path;
- exact mask path;
- target text;
- seed;
- fixed generation parameters;
- four strength values;
- output paths;
- inference time for each output;
- any model warnings/errors.

If practical, create one simple side-by-side comparison image containing:
- reference;
- strength 0.3;
- strength 0.5;
- strength 0.7;
- strength 1.0.

Do not score or auto-select a winner. The user will visually judge:
1. whether the text is actually 苏航268;
2. whether the original SLP style is preserved;
3. whether glyphs/digits look natural;
4. whether the whole image still looks like a real SLP.

## Stop condition

Stop immediately after the four outputs and review evidence are produced.

Out of scope:
- changing the mask;
- changing the reference;
- trying additional target strings;
- seed sweep;
- prompt sweep;
- font/style conditioning experiments;
- OCR verification;
- batch generation;
- synthetic-data pipeline;
- Qwen comparison;
- downstream SLPR training.

Update .ai-bridge/agent-status.md with the exact parameters and output paths for review.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
