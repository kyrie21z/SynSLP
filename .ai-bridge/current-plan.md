# Build local character bbox annotation tool

Updated: 2026-09-22T10:29:54.033Z
Workspace: /home/kyrie/cxprojects/SynSLP
Target agent: Codex (codex)

## Plan

# Goal

Build the minimum sufficient **local web annotation tool** for SynSLP character-level annotations by reusing as much code as practical from the existing local project:

`/home/kyrie/cxprojects/SLPAnnotation`

The tool is for annotating:
- one bounding box per visible character/glyph;
- the text inside each box;
- character reading order.

Annotation is performed **locally**. The resulting annotation artifact is saved locally first, then explicitly synchronized to `server-zyx` as a separate step.

Do not couple annotation UI, AnyText2 inference, GPU/server execution, mask generation, or synthetic-data generation.

# First-principles constraints

The annotation artifact must preserve only source-of-truth human labels:

[
	ext{image} + 	ext{original-pixel bbox} + 	ext{character text} + 	ext{order}
]

Do NOT store derived AnyText2 artifacts such as:
- edit masks;
- font-hint masks;
- padded/dilated boxes;
- 512x512 coordinates;
- letterbox coordinates;
- generated images.

Those must be derived later from the raw annotations so mask policies can change without re-annotation.

All bbox coordinates must be saved in **original image pixel coordinates**, independent of browser zoom/display size.

# Step 1 — Read-only reuse audit of SLPAnnotation

Before writing implementation code, inspect `/home/kyrie/cxprojects/SLPAnnotation` read-only.

Identify the exact existing technology stack and reusable modules for:
1. image loading/navigation;
2. canvas/image rendering and bbox drawing;
3. bbox selection/move/resize/delete interactions;
4. text/label editing;
5. annotation persistence/loading;
6. keyboard shortcuts and progress state;
7. any existing backend routes or local file APIs.

Record in `.ai-bridge/agent-status.md`:
- framework(s) and entry points;
- files/modules worth reusing;
- whether reuse should be direct copy, small adaptation, or not reused;
- any license/config/runtime constraints;
- the smallest implementation path for SynSLP.

Hard rules:
- do not modify `SLPAnnotation`;
- do not redesign from scratch before completing this audit;
- if `SLPAnnotation` is inaccessible from the executor environment, stop and report the blocker rather than inventing its structure.

# Step 2 — Implement the smallest local annotation MVP in SynSLP

Implement inside the SynSLP repository, following the audited SLPAnnotation stack/conventions where practical.

The MVP must support exactly these operations:

1. **Image navigation**
   - load images from a configurable local image directory;
   - next / previous image;
   - show current index and total count;
   - preserve current annotation when navigating.

2. **Bounding-box annotation**
   - drag to create a rectangular bbox;
   - select an existing bbox;
   - move and resize it;
   - delete it;
   - display each box's text label visibly.

3. **Text + order**
   - every bbox stores its text;
   - intended use is one character/glyph per box;
   - assign deterministic reading order;
   - allow correcting text and order after creation.

4. **Persistence**
   - auto-save locally after meaningful edits;
   - reload annotations exactly after browser refresh/restart;
   - no database unless the reused SLPAnnotation implementation already uses one and reuse is materially simpler than file persistence.

5. **Coordinate correctness**
   - browser/display coordinates are converted back to original image pixel coordinates before persistence;
   - zoom/responsive display must not change saved annotations.

Do not add authentication, multi-user collaboration, cloud storage, task assignment, review workflows, OCR-assisted labeling, model inference, or UI theming.

# Step 3 — Freeze a simple annotation schema

Use one canonical local artifact, preferably JSONL unless the reused application has an equally simple established format.

Each image record must contain at least:

```json
{
  "image": "relative/or/stable/image/path.jpg",
  "width": 239,
  "height": 57,
  "instances": [
    {
      "bbox": [12, 8, 43, 50],
      "text": "东",
      "order": 0
    }
  ]
}
```

Requirements:
- bbox convention must be explicitly documented, e.g. `[x1, y1, x2, y2]`;
- define whether `x2/y2` are inclusive or exclusive and keep it consistent;
- coordinates are integers in original image pixels;
- reject/clamp boxes outside image bounds deterministically;
- no duplicate hidden coordinate system;
- stable ordering when records are rewritten.

If the reused SLPAnnotation format differs, add a thin export/conversion layer rather than forcing a large rewrite.

# Step 4 — Add explicit local-to-server sync as a separate utility

Only after the local MVP works, add the smallest explicit sync mechanism for annotation artifacts.

Target:
- host: `server-zyx`
- repo: `/mnt/data/zyx/SynSLP`

Requirements:
- synchronization is invoked explicitly by the user, not automatically by the web app;
- sync only annotation artifacts/config needed by downstream processing;
- do not sync browser caches, local environment files, source images unless explicitly required;
- never overwrite unrelated server data;
- use an existing safe project sync convention if one already exists; otherwise a small documented `rsync/scp` helper is sufficient;
- include a dry-run or clear destination echo before transfer if practical.

Do not trigger AnyText2 after sync.

# Step 5 — Acceptance test on 东泰168

Use the existing local reference image if present:

`reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg`

If that exact local path is unavailable, use one representative local SLP image and record the substitution.

Human/MVP acceptance flow:

1. start the local web app;
2. open the image;
3. create five boxes for `东 / 泰 / 1 / 6 / 8`;
4. assign corresponding text and reading order;
5. save/autosave;
6. refresh/restart;
7. verify all five boxes, text labels, and order restore exactly;
8. verify persisted coordinates map to the original image dimensions;
9. edit one box and delete/recreate one box to verify update semantics;
10. export/finalize the annotation artifact;
11. run the explicit sync utility to the server destination and verify the artifact exists there unchanged.

Record exact commands, output paths, annotation file path, and verification evidence in `.ai-bridge/agent-status.md`.

# Optional but valuable focused test

If it is trivial after the MVP is working, add one small deterministic utility/test that converts selected annotated bboxes into a binary mask in original image coordinates, solely to prove the annotation schema is downstream-usable.

For `东泰168`, demonstrate that selecting:
- `1`;
- `泰`;
- `泰168`;
- `东泰168`;

produces masks aligned to the annotated boxes.

This utility must remain separate from the annotation web app and must not introduce AnyText2 inference.

Skip this if it materially expands scope.

# Expected repository shape

Prefer the structure already used by the reused SLPAnnotation code. If no natural structure exists, keep additions minimal, for example:

```text
SynSLP/
├── annotation_app/          # only if needed by reused stack
├── annotations/             # gitignore generated local annotation data if appropriate
├── scripts/
│   └── sync_annotations_to_server.sh
└── docs/ or README section  # minimal run/use instructions
```

Do not create a complex package hierarchy without evidence that the reused code requires it.

# Stop conditions

Stop when:
- the local bbox+text annotation MVP works;
- refresh/restart persistence is verified;
- original-pixel coordinates are verified;
- the annotation artifact is explicitly synchronized to server successfully;
- evidence is recorded.

Out of scope:
- AnyText2 generation;
- edit-mask policy tuning;
- font-hint-mask policy tuning;
- 512x512 letterboxing;
- OCR auto-labeling;
- automatic character segmentation;
- batch synthetic generation;
- dataset filtering;
- downstream SLPR training;
- annotation platform user accounts;
- multi-annotator review/QA;
- production deployment.

# Implementation contract

- Reuse before rewriting.
- Keep `SLPAnnotation` read-only.
- Work in small, reviewable steps.
- Do not silently change the agreed annotation schema or coordinate convention.
- Run focused verification.
- Update `.ai-bridge/agent-status.md` with files reused/copied, files created/changed, commands, checks, results, blockers, and exact annotation/sync artifact paths.
- Save the final review diff to `.ai-bridge/implementation-diff.patch` when practical.
- Append notable execution events to `.ai-bridge/execution-log.jsonl` when supported.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
