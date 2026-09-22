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

## Character-Level BBox Annotation Tool

Lightweight, dependency-free local web tool for annotating character bounding boxes, labels, and reading order on SLP images. Reuses patterns from `SLPAnnotation` with zero npm/build steps and stdlib Python backend.

### 1. Launch the Annotation Web App

```bash
python scripts/run_annotation_tool.py --image-dir reference/ --port 8767
```

Access the UI in your browser at `http://127.0.0.1:8767`.

### 2. Interaction & Shortcuts

- **Left Drag**: Draw a new rectangular character bounding box (in original image pixel space).
- **Corner Handles**: Drag any of the 4 corner handles of the selected box to resize.
- **Move Box**: Toggle to Select/Move mode (`D`), then drag inside the box to reposition.
- **D**: Toggle between *Draw Mode* and *Select/Move Mode*.
- **Delete / Backspace**: Delete the currently selected character box.
- **PageUp / PageDown**: Navigate to previous / next image (flushes pending saves).
- **Auto-Save**: Changes debounced and saved to JSONL automatically after 400ms (or `Ctrl+S` / `Cmd+S` for manual save).

### 3. Annotation Schema & Coordinates

Saved in `annotations/character_annotations.jsonl` (one JSON record per image):

```json
{
  "image": "reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg",
  "width": 239,
  "height": 57,
  "instances": [
    {"bbox": [5, 8, 45, 54], "text": "东", "order": 0},
    {"bbox": [56, 8, 95, 55], "text": "泰", "order": 1},
    {"bbox": [125, 7, 139, 51], "text": "1", "order": 2},
    {"bbox": [158, 7, 183, 56], "text": "6", "order": 3},
    {"bbox": [204, 7, 229, 52], "text": "8", "order": 4}
  ]
}
```

- **Coordinates**: `[x1, y1, x2, y2]` where `(x1, y1)` is the top-left coordinate (inclusive) and `(x2, y2)` is the bottom-right extent (exclusive, width = `x2 - x1`, height = `y2 - y1`).
- All coordinates are strictly integers in original image space, unaffected by canvas zoom or screen scaling.

### 4. Downstream Mask Generator

Generate binary edit masks from character annotations for selected characters or sequences:

```bash
python scripts/generate_character_masks.py \
  --annotations annotations/character_annotations.jsonl \
  --image "reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg" \
  --select "1" "泰" "泰168" "东泰168"
```

### 5. Synchronize Annotations to Server

Explicit local-to-server synchronization utility:

```bash
# Dry run preview
bash scripts/sync_annotations_to_server.sh --dry-run

# Execute sync to server-zyx:/mnt/data/zyx/SynSLP/annotations/
bash scripts/sync_annotations_to_server.sh
```

### 6. Run Tests

```bash
python -m unittest tests/test_annotation_app.py
python scripts/acceptance_test_step5.py
```

## Repository policy

Large model weights, the upstream AnyText2 repository, generated images, and local caches are intentionally excluded from Git.

