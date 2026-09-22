"""
Local HTTP Server for SynSLP character-level bbox annotation.
Reuses lightweight stdlib ThreadingHTTPServer pattern from SLPAnnotation.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import struct
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from annotation_app.store import AnnotationStore

STATIC_DIR = Path(__file__).resolve().parent / "static"
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def get_image_size(path: Path) -> tuple[int, int]:
    """Extract (width, height) using PIL if available, falling back to stdlib struct parsing."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except ImportError:
        pass

    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head.startswith(b"\x89PNG\r\n\x1a\n"):
                w, h = struct.unpack(">II", head[16:24])
                return w, h
            elif head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
                w, h = struct.unpack("<HH", head[6:10])
                return w, h
            elif head.startswith(b"BM"):
                w, h = struct.unpack("<II", head[18:26])
                return abs(w), abs(h)
            elif head.startswith(b"\xff\xd8"):  # JPEG
                f.seek(0)
                f.read(2)
                b = f.read(1)
                while b:
                    while b != b"\xff":
                        b = f.read(1)
                    while b == b"\xff":
                        b = f.read(1)
                    if 0xc0 <= b[0] <= 0xc3 or 0xc9 <= b[0] <= 0xcb:
                        f.read(3)
                        h, w = struct.unpack(">HH", f.read(4))
                        return w, h
                    else:
                        block_len = struct.unpack(">H", f.read(2))[0]
                        f.seek(block_len - 2, 1)
                    b = f.read(1)
    except Exception:
        pass
    return (0, 0)


class AnnotationServer(ThreadingHTTPServer):
    daemon_threads = False
    allow_reuse_address = True

    def __init__(
        self,
        image_dir: Path,
        jsonl_path: Path,
        host: str = "127.0.0.1",
        port: int = 8767,
    ):
        self.image_dir = Path(image_dir).resolve()
        self.jsonl_path = Path(jsonl_path).resolve()
        self.store = AnnotationStore(self.jsonl_path)
        self.images = self._scan_images()
        super().__init__((host, port), AnnotationHandler)

    def _scan_images(self) -> list[dict]:
        if not self.image_dir.exists():
            return []
        files = []
        for path in sorted(self.image_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
                rel_path = path.relative_to(self.image_dir.parent).as_posix()
                record = self.store.get(rel_path)
                has_ann = record is not None and len(record.get("instances", [])) > 0
                files.append(
                    {
                        "path": rel_path,
                        "abs_path": str(path),
                        "filename": path.name,
                        "annotated": has_ann,
                        "instance_count": len(record.get("instances", [])) if record else 0,
                    }
                )
        return files

    def refresh_image_list(self):
        self.images = self._scan_images()


class AnnotationHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        pass

    def send_data(
        self,
        status: int,
        data: bytes,
        content_type: str = "application/json; charset=utf-8",
    ):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_data(status, payload, "application/json; charset=utf-8")

    def do_GET(self):
        try:
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)

            if parsed.path in ("/", "/index.html", "/app.js", "/style.css"):
                fname = "index.html" if parsed.path in ("/", "/index.html") else parsed.path.lstrip("/")
                target = STATIC_DIR / fname
                if not target.exists():
                    self.send_json(404, {"error": "File not found"})
                    return
                mime, _ = mimetypes.guess_type(str(target))
                self.send_data(200, target.read_bytes(), f"{mime or 'text/plain'}; charset=utf-8")
                return

            if parsed.path == "/api/session":
                self.server.refresh_image_list()
                self.send_json(
                    200,
                    {
                        "images": self.server.images,
                        "total": len(self.server.images),
                        "image_dir": str(self.server.image_dir),
                        "jsonl_path": str(self.server.jsonl_path),
                    },
                )
                return

            if parsed.path == "/api/image":
                img_rel = query.get("path", [""])[0]
                img_abs = (self.server.image_dir.parent / img_rel).resolve()
                if not img_abs.exists() or not img_abs.is_file():
                    self.send_json(404, {"error": f"Image not found: {img_rel}"})
                    return
                mime, _ = mimetypes.guess_type(str(img_abs))
                self.send_data(200, img_abs.read_bytes(), mime or "image/jpeg")
                return

            if parsed.path == "/api/annotation":
                img_rel = query.get("path", [""])[0]
                img_abs = (self.server.image_dir.parent / img_rel).resolve()
                if not img_abs.exists():
                    self.send_json(404, {"error": f"Image not found: {img_rel}"})
                    return

                record = self.server.store.get(img_rel)
                if record is None:
                    # Get image dimensions from disk
                    w, h = get_image_size(img_abs)
                    record = {
                        "image": img_rel,
                        "width": w,
                        "height": h,
                        "instances": [],
                    }
                self.send_json(200, record)
                return

            self.send_json(404, {"error": "Endpoint not found"})

        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def do_POST(self):
        try:
            parsed = urlsplit(self.path)
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))

            if parsed.path == "/api/save":
                img_path = body.get("image")
                instances = body.get("instances", [])
                width = body.get("width")
                height = body.get("height")

                if not img_path:
                    self.send_json(400, {"error": "Missing image path"})
                    return

                # Always derive width and height directly from disk image if available
                img_abs = (self.server.image_dir.parent / img_path).resolve()
                if img_abs.exists() and img_abs.is_file():
                    width, height = get_image_size(img_abs)
                elif not width or not height:
                    self.send_json(400, {"error": f"Image not found and no dimensions provided: {img_path}"})
                    return

                saved_record = self.server.store.put(img_path, width, height, instances)
                self.send_json(200, {"status": "saved", "record": saved_record})
                return

            self.send_json(404, {"error": "Endpoint not found"})

        except Exception as e:
            self.send_json(500, {"error": str(e)})


def create_server(
    image_dir: Path,
    jsonl_path: Path,
    host: str = "127.0.0.1",
    port: int = 8767,
) -> AnnotationServer:
    return AnnotationServer(image_dir, jsonl_path, host=host, port=port)
