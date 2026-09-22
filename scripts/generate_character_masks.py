#!/usr/bin/env python3
"""
Utility to generate binary edit masks from character-level annotations.
Proves downstream usability of the annotation schema without coupling to AnyText2.
Uses pure PIL (Image / ImageDraw) for maximum portability without cv2/numpy dependencies.
"""

import argparse
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate binary mask(s) from character bbox annotations."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=ROOT_DIR / "annotations" / "character_annotations.jsonl",
        help="Path to JSONL annotation file",
    )
    parser.add_argument(
        "--image",
        type=str,
        default="reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg",
        help="Image relative or filename key in annotation file",
    )
    parser.add_argument(
        "--select",
        type=str,
        nargs="+",
        default=["1", "泰", "泰168", "东泰168"],
        help="Character text sequence(s) or character list to mask",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "outputs" / "character_masks",
        help="Output directory for generated masks",
    )
    return parser.parse_args()


def load_annotation(jsonl_path: Path, image_key: str):
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Annotations file not found: {jsonl_path}")

    matched_record = None
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("image") == image_key or Path(rec.get("image", "")).name == Path(image_key).name:
                matched_record = rec
                break

    if matched_record is None:
        raise ValueError(f"No annotation record found for image: {image_key}")
    return matched_record


def generate_mask_for_chars(record: dict, chars_to_mask: str) -> tuple[Image.Image, list]:
    w = record["width"]
    h = record["height"]
    instances = record.get("instances", [])

    mask_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask_img)

    target_char_set = set(chars_to_mask)
    matched_boxes = []

    for inst in instances:
        text = inst.get("text", "")
        if text and text in target_char_set:
            x1, y1, x2, y2 = inst["bbox"]
            # In PIL, rectangle [x0, y0, x1, y1] is inclusive
            draw.rectangle([x1, y1, max(x1, x2 - 1), max(y1, y2 - 1)], fill=255)
            matched_boxes.append((text, [x1, y1, x2, y2]))

    return mask_img, matched_boxes


def main():
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    record = load_annotation(args.annotations.resolve(), args.image)
    w = record["width"]
    h = record["height"]
    print("=" * 60)
    print("Generating Character Masks from Annotations")
    print(f"Image:       {record['image']} ({w}x{h})")
    print(f"Total BBoxes in Record: {len(record.get('instances', []))}")
    print("=" * 60)

    for sel in args.select:
        mask_img, boxes = generate_mask_for_chars(record, sel)
        out_filename = f"mask_{sel}.png"
        out_path = output_dir / out_filename
        mask_img.save(out_path)

        # Count active pixels
        raw_bytes = mask_img.tobytes()
        active_px = sum(1 for b in raw_bytes if b > 0)
        total_px = w * h
        pct = (active_px / total_px) * 100
        print(f"Selection '{sel}': matched {len(boxes)} boxes, active pixels {active_px}/{total_px} ({pct:.2f}%)")
        print(f"  -> Saved: {out_path}")

    print("=" * 60)
    print(f"All requested masks successfully generated in {output_dir}")


if __name__ == "__main__":
    main()
