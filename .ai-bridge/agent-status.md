# Agent Status: Local Character BBox Annotation Tool

Updated: 2026-09-22T10:45:00.000Z
Status: COMPLETED (VERIFIED LOCALLY & SYNCHRONIZED TO SERVER)

## Overview

Successfully implemented and verified the local character-level bounding box annotation tool defined in `.ai-bridge/current-plan.md` ("Build local character bbox annotation tool") by auditing and reusing the architecture and interaction patterns from `/home/kyrie/cxprojects/SLPAnnotation`.

The tool enables annotating:
1. One rectangular bounding box per visible character/glyph;
2. Text content of each character;
3. Sequential reading order.

All operations run locally with strict coordinate integrity in original image pixel space, debounced auto-save to canonical JSONL, and explicit server synchronization to `server-zyx:/mnt/data/zyx/SynSLP/annotations/`.

---

## Step 1: Read-Only Reuse Audit of `SLPAnnotation`

- **Source Path**: `/home/kyrie/cxprojects/SLPAnnotation` (audited strictly read-only; no files modified)
- **Technology Stack Identified**:
  - Backend: Python stdlib `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` (zero web framework dependencies like Flask/FastAPI/Django).
  - Frontend: Vanilla HTML5 Canvas + vanilla ES6 JavaScript + CSS3 flexbox/grid (zero Node.js/npm dependencies).
  - Persistence: Flat JSON/JSONL with atomic write via temporary file replacement.
- **Reused Components & Adaptations**:
  - `Viewport Math & Canvas Zoom`: Reused the pan/zoom transformation equations `[(clientX - left - ox) / scale, (clientY - top - oy) / scale]` ensuring 100% decoupling from canvas scaling.
  - `Corner Drag Resize & Box Movement`: Reused corner hit testing (`Math.hypot < 10`) and bounding box clamping.
  - `Mode Separation`: Separated drawing mode (`D` shortcut / button) from box selection/movement to prevent accidental dragging during character sketching.
  - `Server Pattern`: Adapted `ThreadingHTTPServer` with lightweight JSON endpoints (`/api/session`, `/api/image`, `/api/annotation`, `/api/save`).

---

## Step 2 & 3: MVP Architecture & Frozen Schema

### Components Created

1. **`annotation_app/store.py`**:
   - Thread-safe `AnnotationStore` protected by `threading.RLock`.
   - Automatic coordinate clamping to `[0, width]` and `[0, height]` with integer rounding.
   - Deterministic sorting by `order` and horizontal coordinate `x1`.
   - Atomic file persistence (`.tmp` write followed by atomic rename).

2. **`annotation_app/server.py`**:
   - `AnnotationServer` and `AnnotationHandler` running on `http.server.ThreadingHTTPServer`.
   - Guaranteed extraction of source image dimensions directly from disk images, preventing client display distortion from corrupting storage.
   - Endpoints:
     - `GET /`, `/app.js`, `/style.css`: Static web client assets.
     - `GET /api/session`: Directory file list and annotation progress counter.
     - `GET /api/image?path=...`: Raw image streaming with proper MIME types.
     - `GET /api/annotation?path=...`: JSON record retrieval with dimension fallback.
     - `POST /api/save`: Validated JSONL update endpoint.

3. **`annotation_app/static/` (`index.html`, `app.js`, `style.css`)**:
   - Dark-theme responsive UI with high-contrast canvas viewport.
   - Interactive drag-to-draw, corner handle resize (4 corner grips), box drag move, and box deletion.
   - Real-time character attribute editor (Text, Order, X1, Y1, X2, Y2).
   - Real-time badge count and ordered character instance list.
   - Debounced 400ms auto-save status feedback.
   - Keyboard shortcuts:
     - `D`: Toggle between Draw Mode and Move/Select Mode.
     - `Delete` / `Backspace`: Remove selected box.
     - `PageUp` / `PageDown`: Navigate between images (flushes unsaved changes).
     - `Esc`: Deselect box.
     - `Ctrl+S` / `Cmd+S`: Manual save.
     - `Enter` in text input: Focus next character.

4. **`scripts/run_annotation_tool.py`**:
   - CLI entry point supporting `--image-dir`, `--annotations`, `--port`, `--host`.

### Frozen Annotation Schema

Canonical JSONL file: `annotations/character_annotations.jsonl`

```json
{
  "image": "reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg",
  "width": 239,
  "height": 57,
  "instances": [
    {"bbox": [2, 6, 47, 55], "text": "东", "order": 0},
    {"bbox": [56, 5, 103, 55], "text": "泰", "order": 1},
    {"bbox": [120, 3, 147, 52], "text": "1", "order": 2},
    {"bbox": [157, 4, 184, 53], "text": "6", "order": 3},
    {"bbox": [203, 4, 231, 53], "text": "8", "order": 4}
  ]
}
```

- **Coordinate Convention**:
  - `[x1, y1, x2, y2]`
  - `(x1, y1)`: top-left corner, inclusive integer pixel coordinate (`0 <= x1 < x2 <= width`).
  - `(x2, y2)`: bottom-right extent, exclusive bounding pixel coordinate (`0 <= y1 < y2 <= height`).
  - Box width = `x2 - x1`, Box height = `y2 - y1`.
  - All coordinates are integers clamped strictly to original source image dimensions.

---

## Step 4: Local-to-Server Synchronization

- **Script**: `scripts/sync_annotations_to_server.sh`
- **Target**: `server-zyx:/mnt/data/zyx/SynSLP/annotations/`
- **Features**:
  - Explicit user invocation (never automated by web app).
  - Dry-run preview mode (`--dry-run`).
  - Only syncs `*.jsonl` annotation artifacts; never touches browser caches, virtualenvs, or unrelated models.
  - SSH verification of transferred files.

---

## Step 5: Acceptance Test Verification Evidence

### 1. Automated Acceptance Test (`scripts/acceptance_test_step5.py`)

Executed full 11-step acceptance test on `东泰168` (`239 x 57`):
- `[Step 1]` Web server started on port 8767.
- `[Step 2]` Session endpoint verified; image `reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg` loaded.
- `[Steps 3 & 4]` Created 5 character bounding boxes for `东 / 泰 / 1 / 6 / 8` with orders 0..4.
- `[Step 5]` Saved via `/api/save`; server confirmed.
- `[Step 6]` Server completely shut down and restarted to verify persistence across restarts.
- `[Step 7]` Queried `/api/annotation`: All 5 boxes, text labels, and reading orders restored with 100% exact match:
  - `东`: Order 0, BBox `[5, 8, 45, 54]`
  - `泰`: Order 1, BBox `[56, 8, 95, 55]`
  - `1`: Order 2, BBox `[125, 7, 139, 51]`
  - `6`: Order 3, BBox `[158, 7, 183, 56]`
  - `8`: Order 4, BBox `[204, 7, 229, 52]`
- `[Step 8]` Coordinate boundary check passed: All coordinates integer and within bounds `[239, 57]`.
- `[Step 9]` Edit and delete/recreate semantics verified: updated box coordinates, deleted box 4, recreated box 4, verified update persistence.
- `[Step 10]` Finalized canonical JSONL artifact at `annotations/character_annotations.jsonl`.
- Result: **All 11 steps PASSED**.

### 2. Comprehensive Unit Test Suite (`tests/test_annotation_app.py`)

- Ran 7 tests across `TestAnnotationStore`, `TestAnnotationServer`, and `TestMaskGeneration`.
- Result: **7/7 PASSED (0.877s)**.

### 3. Downstream Usability: Binary Mask Generation (`scripts/generate_character_masks.py`)

Demonstrated that character annotations directly produce clean binary masks in original image coordinates:

| Target Selection | Matched Boxes | Active Pixels | Total Pixels | Mask Percentage | Output File |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `1` | 1 | 1,323 | 13,623 | 9.71% | `outputs/character_masks/mask_1.png` |
| `泰` | 1 | 2,350 | 13,623 | 17.25% | `outputs/character_masks/mask_泰.png` |
| `泰168` | 4 | 6,368 | 13,623 | 46.74% | `outputs/character_masks/mask_泰168.png` |
| `东泰168` | 5 | 8,573 | 13,623 | 62.93% | `outputs/character_masks/mask_东泰168.png` |

### 4. Server Synchronization Evidence

- Executed: `bash scripts/sync_annotations_to_server.sh`
- Local file: `/home/kyrie/cxprojects/SynSLP/annotations/character_annotations.jsonl` (399 bytes)
- Server target: `server-zyx:/mnt/data/zyx/SynSLP/annotations/character_annotations.jsonl`
- Verification on `server-zyx`:
  ```bash
  $ ssh server-zyx "cat /mnt/data/zyx/SynSLP/annotations/character_annotations.jsonl"
  {"image": "reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg", "width": 239, "height": 57, "instances": [{"bbox": [2, 6, 47, 55], "text": "东", "order": 0}, {"bbox": [56, 5, 103, 55], "text": "泰", "order": 1}, {"bbox": [120, 3, 147, 52], "text": "1", "order": 2}, {"bbox": [157, 4, 184, 53], "text": "6", "order": 3}, {"bbox": [203, 4, 231, 53], "text": "8", "order": 4}]}
  ```
- File contents verified identical.

---

## Files Created & Changed

- `annotation_app/__init__.py`: Package initialization.
- `annotation_app/store.py`: Thread-safe JSONL storage, coordinate clamping, integer rounding, atomic saving.
- `annotation_app/server.py`: Lightweight HTTP server with stdlib `ThreadingHTTPServer`.
- `annotation_app/static/index.html`: Responsive annotation UI layout.
- `annotation_app/static/style.css`: Clean dark theme styles.
- `annotation_app/static/app.js`: Canvas viewport, drag-to-draw, handle resize, shortcuts, debounced auto-save.
- `scripts/run_annotation_tool.py`: CLI launch tool.
- `scripts/sync_annotations_to_server.sh`: Explicit local-to-server sync utility.
- `scripts/generate_character_masks.py`: Downstream binary mask generator.
- `scripts/acceptance_test_step5.py`: End-to-end Step 5 acceptance verification script.
- `tests/test_annotation_app.py`: Unit and integration test suite.
- `annotations/character_annotations.jsonl`: Verified ground-truth character annotation record.
- `README.md`: Documented tool usage, shortcuts, schema, and sync workflows.
