#!/usr/bin/env python3
"""
Utility to generate binary edit masks from character-level annotations.
Supports canonical order-based instance selection as well as legacy character-value selection.
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
        "--orders",
        type=int,
        nargs="+",
        default=None,
        help="Specific character instance order(s) to mask (canonical selector, e.g. --orders 2)",
    )
    parser.add_argument(
        "--select",
        type=str,
        nargs="+",
        default=None,
        help="Legacy character text sequence(s) to mask (e.g. --select 1 泰 泰168)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "outputs" / "character_masks",
        help="Output directory for generated masks",
    )
    return parser.parse_args()


def load_annotation(jsonl_path: Path, image_key: str) -> dict:
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


def generate_mask_for_orders(record: dict, orders: list[int]) -> tuple[Image.Image, list]:
    """
    Canonical selector: generate binary mask for specific character instance(s) by order.
    Validates that:
    - No duplicate orders exist in the record.
    - All requested orders exist in the record.
    Preserves [x1, y1, x2, y2) bounding box convention.
    """
    w = record["width"]
    h = record["height"]
    instances = record.get("instances", [])

    seen_orders = {}
    for idx, inst in enumerate(instances):
        ord_val = inst.get("order")
        if ord_val in seen_orders:
            raise ValueError(
                f"Duplicate order {ord_val} found in annotation record for image '{record.get('image')}' "
                f"(instances {seen_orders[ord_val]} and {idx})"
            )
        seen_orders[ord_val] = idx

    missing = [o for o in orders if o not in seen_orders]
    if missing:
        raise ValueError(
            f"Requested order(s) {missing} not found in annotation instances. "
            f"Available orders: {sorted(seen_orders.keys())}"
        )

    target_orders = set(orders)
    mask_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask_img)
    matched_boxes = []

    for inst in instances:
        ord_val = inst.get("order")
        if ord_val in target_orders:
            text = inst.get("text", "")
            x1, y1, x2, y2 = inst["bbox"]
            # [x1, y1, x2, y2) -> inclusive drawing coordinates [x1, y1, x2 - 1, y2 - 1]
            draw.rectangle([x1, y1, max(x1, x2 - 1), max(y1, y2 - 1)], fill=255)
            matched_boxes.append((ord_val, text, [x1, y1, x2, y2]))

    # Sort matched boxes by order
    matched_boxes.sort(key=lambda item: item[0])
    return mask_img, matched_boxes


def generate_mask_for_chars(record: dict, chars_to_mask: str) -> tuple[Image.Image, list]:
    """
    Legacy selector: generate binary mask for matching character text values.
    Note: character value != character identity. Use generate_mask_for_orders for canonical selection.
    """
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
    total_px = w * h

    print("=" * 60)
    print("Generating Character Masks from Annotations")
    print(f"Image:                 {record['image']} ({w}x{h})")
    print(f"Total BBoxes in Record:{len(record.get('instances', []))}")
    print("=" * 60)

    # 1. Canonical order-based selection
    if args.orders is not None:
        mask_img, boxes = generate_mask_for_orders(record, args.orders)
        order_str = "_".join(str(o) for o in args.orders)
        out_filename = f"mask_order_{order_str}.png"
        out_path = output_dir / out_filename
        mask_img.save(out_path)

        raw_bytes = mask_img.tobytes()
        active_px = sum(1 for b in raw_bytes if b > 0)
        pct = (active_px / total_px) * 100
        print(f"Order selection {args.orders}: matched {len(boxes)} boxes:")
        for ord_val, text, bbox in boxes:
            box_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            print(f"  - Order {ord_val}: text='{text}', bbox={bbox}, expected_area={box_area}px")
        print(f"Active pixels: {active_px}/{total_px} ({pct:.2f}%)")
        print(f"  -> Saved: {out_path}")

    # 2. Legacy text-based selection
    if args.select is not None:
        for sel in args.select:
            mask_img, boxes = generate_mask_for_chars(record, sel)
            out_filename = f"mask_{sel}.png"
            out_path = output_dir / out_filename
            mask_img.save(out_path)

            raw_bytes = mask_img.tobytes()
            active_px = sum(1 for b in raw_bytes if b > 0)
            pct = (active_px / total_px) * 100
            print(f"Text selection '{sel}': matched {len(boxes)} boxes, active pixels {active_px}/{total_px} ({pct:.2f}%)")
            print(f"  -> Saved: {out_path}")

    # If neither specified, default to --orders 2 (order-2 single character mask)
    if args.orders is None and args.select is None:
        mask_img, boxes = generate_mask_for_orders(record, [2])
        out_path = output_dir / "mask_order_2.png"
        mask_img.save(out_path)
        raw_bytes = mask_img.tobytes()
        active_px = sum(1 for b in raw_bytes if b > 0)
        pct = (active_px / total_px) * 100
        print(f"Default order selection [2]: matched {len(boxes)} boxes:")
        for ord_val, text, bbox in boxes:
            box_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            print(f"  - Order {ord_val}: text='{text}', bbox={bbox}, expected_area={box_area}px")
        print(f"Active pixels: {active_px}/{total_px} ({pct:.2f}%)")
        print(f"  -> Saved: {out_path}")

    print("=" * 60)
    print(f"All requested masks successfully generated in {output_dir}")


if __name__ == "__main__":
    main()
