#!/usr/bin/env python3
"""
CLI entry point to launch the local character-level annotation web tool for SynSLP.
"""

import argparse
import sys
from pathlib import Path

# Ensure SynSLP repo root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from annotation_app.server import create_server


def parse_args():
    parser = argparse.ArgumentParser(
        description="Launch SynSLP local character-level bbox annotation tool."
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=ROOT_DIR / "reference",
        help="Directory containing images to annotate (default: reference/)",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=ROOT_DIR / "annotations" / "character_annotations.jsonl",
        help="Target JSONL file for storing annotations (default: annotations/character_annotations.jsonl)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8767,
        help="Local port to listen on (default: 8767)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Listen address (default: 127.0.0.1)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    image_dir = args.image_dir.resolve()
    annotations_file = args.annotations.resolve()

    if not image_dir.exists():
        print(f"[SynSLP] Creating image directory: {image_dir}")
        image_dir.mkdir(parents=True, exist_ok=True)

    annotations_file.parent.mkdir(parents=True, exist_ok=True)

    server = create_server(
        image_dir=image_dir,
        jsonl_path=annotations_file,
        host=args.host,
        port=args.port,
    )

    print("=" * 65)
    print(f"SynSLP Character-Level BBox Annotation Tool")
    print(f"URL:             http://{args.host}:{args.port}")
    print(f"Image Directory: {image_dir} ({len(server.images)} images found)")
    print(f"Annotations:     {annotations_file}")
    print("=" * 65)
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
