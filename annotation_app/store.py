"""
JSONL storage and validation for character-level SLP annotations.

Coordinate Convention:
- Bounding box format: [x1, y1, x2, y2]
- x1, y1: top-left corner, inclusive integer pixel coordinate (0 <= x1 < x2 <= width)
- x2, y2: bottom-right extent, exclusive integer pixel boundary (0 <= y1 < y2 <= height)
- Box width = x2 - x1, Box height = y2 - y1
- Clamped strictly to [0, width] and [0, height] of the original source image
- Independent of browser viewport, zoom factor, or display resolution
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image


class AnnotationStore:
    def __init__(self, jsonl_path: Path):
        self.jsonl_path = Path(jsonl_path)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._records: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        """Load all records from JSONL file if it exists."""
        with self._lock:
            self._records.clear()
            if not self.jsonl_path.exists():
                return

            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        img_key = data.get("image")
                        if img_key:
                            self._records[img_key] = data
                    except json.JSONDecodeError:
                        continue

    def save_all(self) -> None:
        """Atomically persist all records to JSONL file."""
        with self._lock:
            tmp_path = self.jsonl_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                for _, record in sorted(self._records.items()):
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            tmp_path.replace(self.jsonl_path)

    def get(self, image_path: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._records.get(image_path)
            return json.loads(json.dumps(rec)) if rec else None

    def put(
        self,
        image_path: str,
        width: int,
        height: int,
        instances: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Validate, clamp, sort and store an image's character annotations.
        Each instance:
          bbox: [x1, y1, x2, y2]
          text: str
          order: int
        """
        validated_instances = []
        for idx, inst in enumerate(instances):
            raw_box = inst.get("bbox", [])
            if len(raw_box) != 4:
                continue

            x1 = max(0, min(width, int(round(raw_box[0]))))
            y1 = max(0, min(height, int(round(raw_box[1]))))
            x2 = max(0, min(width, int(round(raw_box[2]))))
            y2 = max(0, min(height, int(round(raw_box[3]))))

            # Ensure x1 < x2, y1 < y2
            left = min(x1, x2)
            right = max(x1, x2)
            top = min(y1, y2)
            bottom = max(y1, y2)

            if right - left < 1 or bottom - top < 1:
                continue

            text = str(inst.get("text", "")).strip()
            order = inst.get("order", idx)
            try:
                order = int(order)
            except (ValueError, TypeError):
                order = idx

            validated_instances.append(
                {
                    "bbox": [left, top, right, bottom],
                    "text": text,
                    "order": order,
                }
            )

        # Sort instances deterministically by order, then left coordinate
        validated_instances.sort(key=lambda item: (item["order"], item["bbox"][0]))

        record = {
            "image": image_path,
            "width": width,
            "height": height,
            "instances": validated_instances,
        }
        with self._lock:
            self._records[image_path] = record
            self.save_all()
        return record
