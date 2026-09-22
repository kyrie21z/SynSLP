# SynSLP

Synthetic Ship License Plate (SLP) data generation utilities.

Current stage: deploy an **off-the-shelf AnyText2** editor first. We are not modifying or training the text-image editing model itself.

## AnyText2 deployment

Upstream:
- Code: https://github.com/tyxsspa/AnyText2
- Checkpoint: ModelScope `iic/cv_anytext2`
- Pinned upstream commit: `b06c583a583818f3679665ef67b51363f107853c`

### 1. Install

```bash
cd /home/kyrie/cxprojects/SynSLP
bash scripts/setup_anytext2.sh
```

The script creates the official Conda environment `anytext2`, clones the pinned upstream source into `third_party/AnyText2`, and downloads the official checkpoint into `third_party/AnyText2/models`.

### 2. Verify

```bash
bash scripts/check_anytext2.sh
```

Expected result: CUDA is visible, `models/anytext_v2.0.ckpt` exists, and the AnyText2 model initializes successfully in FP16.

### 3. Launch the official demo

```bash
bash scripts/run_anytext2_demo.sh
```

By default the Chinese-to-English **image-prompt translator is disabled** to save VRAM. Chinese target text inside quoted text prompts is still supported by AnyText2.

To enable the translator:

```bash
USE_TRANSLATOR=1 bash scripts/run_anytext2_demo.sh
```

## Repository policy

Large model weights, the upstream AnyText2 repository, generated images, and local caches are intentionally excluded from Git.
