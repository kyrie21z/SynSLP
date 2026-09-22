#!/usr/bin/env python3
"""
End-to-end Step 5 acceptance test script for SynSLP character-level annotation tool.
Executes the full human/MVP acceptance flow defined in .ai-bridge/current-plan.md.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from annotation_app.server import create_server
from annotation_app.store import AnnotationStore

IMG_REL = "reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg"
JSONL_PATH = ROOT_DIR / "annotations" / "character_annotations.jsonl"
PORT = 8767
HOST = "127.0.0.1"


def main():
    print("=" * 65)
    print("SynSLP Step 5 Acceptance Test on 东泰168")
    print("=" * 65)

    # 1. Start web server
    print("\n[Step 1] Starting annotation server...")
    server = create_server(
        image_dir=ROOT_DIR / "reference",
        jsonl_path=JSONL_PATH,
        host=HOST,
        port=PORT,
    )
    import threading
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)
    print(f"  -> Server running at http://{HOST}:{PORT}")

    # 2. Open image & session check
    print("\n[Step 2] Querying /api/session...")
    req = Request(f"http://{HOST}:{PORT}/api/session")
    with urlopen(req) as res:
        assert res.status == 200
        session_data = json.loads(res.read().decode())
    print(f"  -> Total images: {session_data['total']}")
    found = any(item["path"] == IMG_REL for item in session_data["images"])
    assert found, f"Image {IMG_REL} not found in session!"
    print(f"  -> Image found in session: {IMG_REL}")

    # 3 & 4. Create five boxes for 东 / 泰 / 1 / 6 / 8 and assign text & order
    print("\n[Steps 3 & 4] Creating annotations for 东 / 泰 / 1 / 6 / 8...")
    test_instances = [
        {"bbox": [5, 8, 45, 54], "text": "东", "order": 0},
        {"bbox": [56, 8, 95, 55], "text": "泰", "order": 1},
        {"bbox": [125, 7, 139, 51], "text": "1", "order": 2},
        {"bbox": [158, 7, 183, 56], "text": "6", "order": 3},
        {"bbox": [204, 7, 229, 52], "text": "8", "order": 4},
    ]

    # 5. Save/autosave via API
    print("\n[Step 5] Saving annotations to /api/save...")
    save_payload = {
        "image": IMG_REL,
        "width": 239,
        "height": 57,
        "instances": test_instances,
    }
    req = Request(
        f"http://{HOST}:{PORT}/api/save",
        data=json.dumps(save_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as res:
        assert res.status == 200
        save_res = json.loads(res.read().decode())
        assert save_res["status"] == "saved"
    print("  -> Save confirmed by server API.")

    # 6. Restart server / reload
    print("\n[Step 6] Shutting down and restarting server to simulate refresh/restart...")
    server.shutdown()
    server.server_close()
    time.sleep(0.3)

    server2 = create_server(
        image_dir=ROOT_DIR / "reference",
        jsonl_path=JSONL_PATH,
        host=HOST,
        port=PORT,
    )
    t2 = threading.Thread(target=server2.serve_forever, daemon=True)
    t2.start()
    time.sleep(0.5)

    # 7. Verify all five boxes, text labels, and order restore exactly
    print("\n[Step 7] Querying /api/annotation after restart...")
    from urllib.parse import quote
    encoded_rel = quote(IMG_REL)
    req = Request(f"http://{HOST}:{PORT}/api/annotation?path={encoded_rel}")
    with urlopen(req) as res:
        assert res.status == 200
        reloaded = json.loads(res.read().decode())

    assert len(reloaded["instances"]) == 5, f"Expected 5 instances, got {len(reloaded['instances'])}"
    for orig, loaded in zip(test_instances, reloaded["instances"]):
        assert orig["text"] == loaded["text"], f"Text mismatch: {orig['text']} vs {loaded['text']}"
        assert orig["order"] == loaded["order"], f"Order mismatch: {orig['order']} vs {loaded['order']}"
        assert orig["bbox"] == loaded["bbox"], f"BBox mismatch: {orig['bbox']} vs {loaded['bbox']}"
        print(f"  [Verified] Glyph '{loaded['text']}': Order {loaded['order']}, BBox {loaded['bbox']}")

    # 8. Verify persisted coordinates map to original image dimensions
    print("\n[Step 8] Verifying original coordinate bounds...")
    w = reloaded["width"]
    h = reloaded["height"]
    assert w == 239 and h == 57, f"Dimensions mismatch: {w}x{h}"
    for inst in reloaded["instances"]:
        x1, y1, x2, y2 = inst["bbox"]
        assert 0 <= x1 < x2 <= w, f"Invalid X bounds: {x1}, {x2} for width {w}"
        assert 0 <= y1 < y2 <= h, f"Invalid Y bounds: {y1}, {y2} for height {h}"
    print(f"  -> All bounding boxes strictly within image bounds [239, 57].")

    # 9. Edit one box and delete/recreate one box to verify update semantics
    print("\n[Step 9] Testing edit and delete/recreate semantics...")
    edited_instances = [inst.copy() for inst in reloaded["instances"]]
    # Edit box 0 (东) slightly: [5, 8, 46, 54]
    edited_instances[0]["bbox"] = [5, 8, 46, 54]
    # Delete box 4 (8)
    del edited_instances[4]
    # Recreate box 4 with order 4
    edited_instances.append({"bbox": [203, 7, 229, 53], "text": "8", "order": 4})

    save_payload["instances"] = edited_instances
    req = Request(
        f"http://{HOST}:{PORT}/api/save",
        data=json.dumps(save_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as res:
        assert res.status == 200

    # Verify update
    req = Request(f"http://{HOST}:{PORT}/api/annotation?path={encoded_rel}")
    with urlopen(req) as res:
        updated = json.loads(res.read().decode())
    assert len(updated["instances"]) == 5
    assert updated["instances"][0]["bbox"] == [5, 8, 46, 54]
    assert updated["instances"][4]["bbox"] == [203, 7, 229, 53]
    print("  -> Update semantics verified (edit + delete/recreate).")

    # 10. Export/finalize annotation artifact (restore canonical clean boxes)
    print("\n[Step 10] Finalizing canonical annotation record...")
    save_payload["instances"] = test_instances
    req = Request(
        f"http://{HOST}:{PORT}/api/save",
        data=json.dumps(save_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req) as res:
        assert res.status == 200

    server2.shutdown()
    server2.server_close()

    print(f"  -> Canonical JSONL artifact saved at: {JSONL_PATH}")
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        print("  -> JSONL Content:")
        for line in f:
            print(f"     {line.strip()}")

    print("\n" + "=" * 65)
    print("Acceptance test on 东泰168 successfully passed all checks!")
    print("=" * 65)


if __name__ == "__main__":
    main()
