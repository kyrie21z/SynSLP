"""
Unit and integration tests for SynSLP character-level annotation tool.
"""

import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image

from annotation_app.server import create_server
from annotation_app.store import AnnotationStore
from scripts.generate_character_masks import generate_mask_for_chars


class TestAnnotationStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.jsonl_path = self.temp_dir / "annotations.jsonl"
        self.store = AnnotationStore(self.jsonl_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_put_and_get(self):
        instances = [
            {"bbox": [10.2, 5.8, 40.1, 48.9], "text": "东", "order": 0},
            {"bbox": [50.0, 5.0, 90.0, 50.0], "text": "泰", "order": 1},
        ]
        rec = self.store.put("test.jpg", 239, 57, instances)
        self.assertEqual(rec["image"], "test.jpg")
        self.assertEqual(rec["width"], 239)
        self.assertEqual(rec["height"], 57)
        self.assertEqual(len(rec["instances"]), 2)
        # Coordinate clamping and integer casting
        self.assertEqual(rec["instances"][0]["bbox"], [10, 6, 40, 49])
        self.assertEqual(rec["instances"][0]["text"], "东")
        self.assertEqual(rec["instances"][0]["order"], 0)

        # Retrieve and verify
        got = self.store.get("test.jpg")
        self.assertIsNotNone(got)
        self.assertEqual(got, rec)

    def test_clamping_and_ordering(self):
        # Out of bounds and reversed coordinates
        instances = [
            {"bbox": [200, 10, 150, 40], "text": "6", "order": 3},
            {"bbox": [-10, -5, 300, 100], "text": "全", "order": 0},
        ]
        rec = self.store.put("clamp.jpg", 200, 50, instances)
        # Order 0 first
        self.assertEqual(rec["instances"][0]["order"], 0)
        self.assertEqual(rec["instances"][0]["bbox"], [0, 0, 200, 50])
        # Order 3 second, normalized x1 < x2
        self.assertEqual(rec["instances"][1]["order"], 3)
        self.assertEqual(rec["instances"][1]["bbox"], [150, 10, 200, 40])

    def test_persistence_reload(self):
        instances = [
            {"bbox": [5, 8, 45, 54], "text": "东", "order": 0},
            {"bbox": [56, 8, 95, 55], "text": "泰", "order": 1},
            {"bbox": [125, 7, 139, 51], "text": "1", "order": 2},
            {"bbox": [158, 7, 183, 56], "text": "6", "order": 3},
            {"bbox": [204, 7, 229, 52], "text": "8", "order": 4},
        ]
        self.store.put("ref.jpg", 239, 57, instances)

        # Create fresh store instance on same file
        new_store = AnnotationStore(self.jsonl_path)
        rec = new_store.get("ref.jpg")
        self.assertIsNotNone(rec)
        self.assertEqual(len(rec["instances"]), 5)
        texts = [inst["text"] for inst in rec["instances"]]
        self.assertEqual(texts, ["东", "泰", "1", "6", "8"])


class TestAnnotationServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.img_dir = cls.temp_dir / "images"
        cls.img_dir.mkdir(parents=True)
        # Create test image
        cls.img_path = cls.img_dir / "test_plate.jpg"
        im = Image.new("RGB", (239, 57), color=(20, 30, 80))
        im.save(cls.img_path)

        cls.jsonl_path = cls.temp_dir / "annotations.jsonl"
        cls.port = 8789
        cls.server = create_server(cls.img_dir, cls.jsonl_path, host="127.0.0.1", port=cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_static_files(self):
        for path in ["/", "/index.html", "/app.js", "/style.css"]:
            url = f"http://127.0.0.1:{self.port}{path}"
            req = Request(url)
            with urlopen(req) as res:
                self.assertEqual(res.status, 200)
                content = res.read()
                self.assertGreater(len(content), 50)

    def test_session_and_image(self):
        url = f"http://127.0.0.1:{self.port}/api/session"
        with urlopen(url) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode())
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["images"][0]["filename"], "test_plate.jpg")

        img_rel = data["images"][0]["path"]
        img_url = f"http://127.0.0.1:{self.port}/api/image?path={img_rel}"
        with urlopen(img_url) as res:
            self.assertEqual(res.status, 200)
            bytes_data = res.read()
            self.assertGreater(len(bytes_data), 100)

    def test_save_and_restore(self):
        save_url = f"http://127.0.0.1:{self.port}/api/save"
        payload = {
            "image": "images/test_plate.jpg",
            "instances": [
                {"bbox": [10, 10, 50, 50], "text": "苏", "order": 0},
                {"bbox": [60, 10, 100, 50], "text": "A", "order": 1},
            ],
        }
        req = Request(
            save_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as res:
            self.assertEqual(res.status, 200)
            res_data = json.loads(res.read().decode())
            self.assertEqual(res_data["status"], "saved")
            self.assertEqual(res_data["record"]["width"], 239)
            self.assertEqual(res_data["record"]["height"], 57)

        # GET annotation
        get_url = f"http://127.0.0.1:{self.port}/api/annotation?path=images/test_plate.jpg"
        with urlopen(get_url) as res:
            self.assertEqual(res.status, 200)
            rec = json.loads(res.read().decode())
            self.assertEqual(len(rec["instances"]), 2)
            self.assertEqual(rec["instances"][0]["text"], "苏")
            self.assertEqual(rec["instances"][1]["text"], "A")


class TestMaskGeneration(unittest.TestCase):
    def test_generate_masks(self):
        record = {
            "image": "reference/dongtai.jpg",
            "width": 239,
            "height": 57,
            "instances": [
                {"bbox": [5, 8, 45, 54], "text": "东", "order": 0},
                {"bbox": [56, 8, 95, 55], "text": "泰", "order": 1},
                {"bbox": [125, 7, 139, 51], "text": "1", "order": 2},
                {"bbox": [158, 7, 183, 56], "text": "6", "order": 3},
                {"bbox": [204, 7, 229, 52], "text": "8", "order": 4},
            ],
        }
        # Mask single char "1"
        mask1, boxes1 = generate_mask_for_chars(record, "1")
        self.assertEqual(mask1.size, (239, 57))
        self.assertEqual(len(boxes1), 1)
        self.assertEqual(boxes1[0][0], "1")

        # Mask "泰168"
        mask_tai168, boxes_tai168 = generate_mask_for_chars(record, "泰168")
        self.assertEqual(len(boxes_tai168), 4)

        # Mask "东泰168"
        mask_all, boxes_all = generate_mask_for_chars(record, "东泰168")
        self.assertEqual(len(boxes_all), 5)


if __name__ == "__main__":
    unittest.main()
