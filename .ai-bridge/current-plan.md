# Sync SynSLP and deploy AnyText2

Updated: 2026-09-22T03:56:46.552Z
Workspace: /home/kyrie/cxprojects/SynSLP
Target agent: Codex (codex)

## Plan

# Goal

Establish SynSLP as one consistent Git repository across local, GitHub, and server, then deploy and minimally validate the official AnyText2 on server. Execute strictly in this order. Do not start a later stage until the previous stage is verified.

## 1. Establish local ↔ GitHub Git baseline

Local root:
- /home/kyrie/cxprojects/SynSLP

GitHub:
- kyrie21z/SynSLP

Current known fact:
- The local root exists but is not currently a Git repository.
- Do not assume the remote is empty or assume any previously reported commit hash is still current; inspect GitHub/remote state first.

Actions:
- Inspect local files, including hidden files, before any Git initialization or clone.
- If local contains user files, preserve them; do not delete, overwrite, hard-reset, or force-push.
- Inspect the GitHub repository and default branch.
- Establish origin and main so local and GitHub contain the union of intended project files without losing either side.
- Prefer normal Git history; if remote already has history, integrate safely instead of recreating it.
- End with a clean working tree and local HEAD == origin/main.

Verification:
- local is a Git repository on branch main
- origin points to kyrie21z/SynSLP
- working tree clean
- local HEAD == origin/main

## 2. Sync GitHub → server

Target:
- server-zyx:/mnt/data/zyx/SynSLP

Actions:
- Connect to server-zyx.
- If target does not exist, clone from GitHub.
- If target exists, inspect status first and preserve any uncommitted or unique server-side work.
- Safely align server main with GitHub main.
- Do not use destructive reset/force operations.
- Do not use whole-repository scp/rsync as a substitute for Git synchronization.

Verification:
- local HEAD == origin/main == server HEAD
- server working tree clean

## 3. Deploy official AnyText2 on server only

Start only after stages 1 and 2 pass.

Upstream:
- https://github.com/tyxsspa/AnyText2

Purpose:
- off-the-shelf synthetic SLP data generator only
- no model architecture changes
- no training or fine-tuning

Deployment constraints:
- Use an isolated environment; prefer conda env name: anytext2.
- Before installing, inspect server GPU, driver/CUDA, free disk space, conda, and Python state.
- Reproduce the official AnyText2 environment as closely as practical; if exact official versions conflict with the server, make the minimum compatibility change and record it.
- Keep third-party source, checkpoints, caches, and generated data out of Git unless a small explicit config/launcher is intentionally part of SynSLP.
- Prefer FP16 inference where supported.
- Disable optional prompt-translation components if they materially increase VRAM and are not needed for Chinese target-text editing.
- Use the official/public checkpoint referenced by the AnyText2 project; record exact source and revision when possible.

## 4. Minimal deployment acceptance test

Prove functionality, not just installation.

Required checks:
1. AnyText2 checkpoint loads successfully.
2. CUDA inference runs successfully.
3. A stock/example inference produces an output image.
4. One Chinese ship-license-plate-oriented reference edit smoke test succeeds:
   - reference image
   - explicit text region/mask as required by AnyText2
   - Chinese + digits target string
   - saved edited output

Record in repo-visible notes or deployment metadata:
- GPU model / VRAM
- Python, PyTorch, CUDA versions
- AnyText2 upstream commit/revision
- checkpoint source/revision
- exact smoke-test command/config
- input/output paths
- encountered errors and the minimal fixes applied

## Stop condition

Stop immediately after the smoke test is reproducibly successful.

Out of scope:
- batch synthesis pipeline
- OCR exact-match filtering
- dataset sampling policy
- Qwen-Image-Edit
- AnyText2 training/fine-tuning
- model comparison or downstream SLPR training

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
