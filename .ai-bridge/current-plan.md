# Close AnyText2 deployment reproducibility gaps

Updated: 2026-09-22T06:07:46.155Z
Workspace: /home/kyrie/cxprojects/SynSLP
Target agent: Codex (codex)

## Plan

# Goal

Close the two remaining acceptance gaps from the previous AnyText2 deployment without expanding scope:

1. make the server-side AnyText2 compatibility fixes reproducible from repository-controlled deployment assets;
2. restore final Git consistency so local HEAD == origin/main == server HEAD.

Do not add batch synthesis, OCR filtering, Qwen, model comparison, training, or dataset-generation logic.

## 1. Capture the exact deployed compatibility delta

Current known deployment:
- SynSLP local: /home/kyrie/cxprojects/SynSLP
- SynSLP server: server-zyx:/mnt/data/zyx/SynSLP
- AnyText2 upstream commit: b06c583a583818f3679665ef67b51363f107853c
- AnyText2 server checkout: /mnt/data/zyx/SynSLP/third_party/AnyText2
- conda env: anytext2

Known manual compatibility fixes from the completed deployment:
- setuptools 69.5.1 / setuptools<70
- numpy==1.24.4
- pytorch-lightning==1.9.5 / <2.0
- Pillow==9.5.0
- ldm/modules/attention.py: cast softmax similarity to v.dtype in fallback CrossAttention
- ms_wrapper.py: defensive sort_priority fallback used by the working server deployment

Actions:
- Inspect the actual server AnyText2 git diff against the pinned upstream commit.
- Inspect the actual installed versions in the working anytext2 environment.
- Treat the working server deployment as the source of truth for compatibility changes; do not invent additional patches.
- Reduce the captured delta to only what is required for the verified deployment.

Acceptance:
- exact source-code delta and package-version delta are known and reviewable before changing deployment automation.

## 2. Encode reproducibility in SynSLP

Make the smallest repository-controlled change that can recreate the working deployment.

Preferred structure:
- store the minimal AnyText2 source compatibility patch under a tracked path such as patches/anytext2/;
- encode required compatibility package pins in a tracked file or directly in setup_anytext2.sh;
- keep third_party/, checkpoints, caches, outputs, and the conda environment untracked.

Update scripts/setup_anytext2.sh so that a fresh deployment deterministically:
1. clones/fetches AnyText2;
2. checks out the pinned upstream commit;
3. creates/updates the isolated conda environment from upstream environment.yaml;
4. enforces only the compatibility package pins proven necessary by the working deployment;
5. applies the tracked compatibility patch idempotently;
6. downloads/verifies the official iic/cv_anytext2 checkpoint;
7. fails clearly on patch/version mismatch instead of silently continuing.

Constraints:
- do not vendor AnyText2 source into SynSLP;
- do not modify model architecture or inference behavior beyond the already-proven compatibility fixes;
- do not rely on undocumented manual edits after setup;
- preserve existing script behavior where it already works;
- keep the patch tied to the pinned AnyText2 commit.

## 3. Verify reproducibility without disturbing the working deployment

Do not destroy or reset the verified anytext2 environment/checkpoint.

Minimum sufficient verification:
- syntax/static check of changed deployment scripts;
- prove the tracked patch cleanly applies to a fresh checkout of the pinned AnyText2 commit;
- prove the encoded dependency constraints resolve to the intended compatibility versions;
- if practical with the existing server resources, use an isolated disposable validation environment/name rather than modifying the working anytext2 environment;
- run the existing check/smoke path against the resulting reproducible deployment when feasible.

Required functional acceptance remains:
- checkpoint loads;
- CUDA + FP16 works;
- stock inference produces an image;
- Chinese + digits SLP reference edit produces an image.

If a full disposable reinstall is disproportionately expensive, do not fake it:
- explicitly record which parts were independently recreated;
- at minimum require fresh-checkout patch application plus dependency-version verification plus rerun of the existing working smoke test.

## 4. Commit, push, and re-sync server

After reproducibility changes pass:
- commit only the intended tracked SynSLP changes;
- push main to origin;
- update server-zyx:/mnt/data/zyx/SynSLP from origin/main using normal Git synchronization;
- preserve untracked third_party/checkpoints/outputs and the working conda environment;
- do not hard reset, force push, or delete deployment artifacts.

Final acceptance:
- local working tree clean;
- server working tree clean for tracked files;
- local HEAD == origin/main == server HEAD;
- setup assets contain all compatibility steps required by the verified AnyText2 deployment;
- existing AnyText2 smoke test still passes after the tracked changes.

## Stop condition

Stop once both original gaps are closed and evidenced:
1. clean deployment reproducibility is encoded and verified to the extent stated above;
2. all three Git endpoints are on the same final commit.

Record in .ai-bridge/agent-status.md:
- final commit SHA on local/origin/server;
- tracked files added/changed;
- exact compatibility patch contents;
- exact dependency pins;
- verification commands and results;
- whether verification used a fresh disposable environment or only fresh-checkout + dependency checks;
- any residual reproducibility limitation.

Do not proceed to synthetic-data pipeline design or generation.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
