"""Private photo storage for manually run workflows (admin-only)."""
import base64
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlparse

MAX_FILE = int(os.getenv("PHOTO_UPLOAD_MAX_FILE_BYTES", "0"))
MAX_BODY = int(os.getenv("PHOTO_UPLOAD_MAX_BODY_BYTES", "0"))
LOCK = threading.Lock()


def origin_allowed(origin, allowed_origin):
    if not origin or origin == allowed_origin:
        return True
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def image_mime(raw, payload, name):
    detected = ("image/png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else
                "image/jpeg" if raw.startswith(b"\xff\xd8\xff") else
                "image/webp" if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP" else
                "image/gif" if raw.startswith((b"GIF87a", b"GIF89a")) else None)
    declared = str(payload.get("mime_type") or payload.get("type") or "").strip().lower()
    guessed = mimetypes.guess_type(name)[0]
    return detected or (declared if declared.startswith("image/") else None) or guessed or "application/octet-stream"


def photo_request(method, path, headers, payload, authorize, allowed_origin):
    if not origin_allowed(headers.get("Origin"), allowed_origin):
        return {"ok": False, "message": "Origin not allowed."}, 403
    ok, body, status = authorize(headers=headers)
    if not ok:
        return body, status
    root = Path(os.getenv("PHOTO_UPLOAD_DIR", str(Path(__file__).parent / "private-photos")))
    try:
        if method == "POST" and path == "/photo-uploads":
            if not isinstance(payload, dict):
                raise ValueError("Invalid upload.")
            raw = base64.b64decode(payload.get("data", ""), validate=True)
            if not raw or (MAX_FILE and len(raw) > MAX_FILE):
                raise ValueError("Invalid photo data.")
            # Files are never executed or served as HTML; content stays behind admin auth.
            name = str(payload.get("name", "photo")).replace("\\", "/").split("/")[-1]
            name = "".join(c for c in name if ord(c) >= 32)[:160] or "photo"
            mime = image_mime(raw, payload, name)
            file_id = secrets.token_hex(20)
            meta = {"id": file_id, "name": name, "mime_type": mime, "size": len(raw),
                    "url": "/ext-api/photo-uploads/" + file_id, "access": "admin-only"}
            with LOCK:
                root.mkdir(mode=0o700, parents=True, exist_ok=True)
                quota = int(os.getenv("PHOTO_UPLOAD_QUOTA_BYTES", "0"))
                if quota and sum(p.stat().st_size for p in root.glob("*.bin")) + len(raw) > quota:
                    return {"ok": False, "message": "Photo storage is full. Remove unused photos first."}, 413
                data_path, meta_path = root / (file_id + ".bin"), root / (file_id + ".json")
                try:
                    data_path.write_bytes(raw)
                    data_path.chmod(0o600)
                    meta_path.write_text(json.dumps(meta), encoding="utf-8")
                    meta_path.chmod(0o600)
                except OSError:
                    data_path.unlink(missing_ok=True)
                    meta_path.unlink(missing_ok=True)
                    raise
            return {"ok": True, "file": meta}, 201
        match = re.fullmatch(r"/photo-uploads/([a-f0-9]{40})", path)
        if not match:
            return {"ok": False, "message": "Not found."}, 404
        file_id = match[1]
        with LOCK:
            data_path, meta_path = root / (file_id + ".bin"), root / (file_id + ".json")
            if not data_path.is_file() or not meta_path.is_file():
                return {"ok": False, "message": "Photo not found. Please upload it again."}, 404
            if method == "DELETE":
                data_path.unlink()
                meta_path.unlink()
                return {"ok": True}, 200
            if method == "GET":
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                return {"ok": True, "file": meta,
                        "data": base64.b64encode(data_path.read_bytes()).decode("ascii")}, 200
        return {"ok": False, "message": "Method not allowed."}, 405
    except (ValueError, TypeError):
        return {"ok": False, "message": "Invalid photo upload."}, 400
    except OSError:
        return {"ok": False, "message": "Photo storage unavailable."}, 503
