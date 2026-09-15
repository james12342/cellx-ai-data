import base64
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from photo_uploads import photo_request


class PhotoUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"PHOTO_UPLOAD_DIR": self.temp.name})
        self.env.start()
        self.headers = {"X-Workflow-Admin-Token": "test", "Origin": "https://app.test"}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def call(self, method="POST", path="/photo-uploads", payload=None, headers=None):
        def authorize(headers):
            return (True, None, 200) if headers.get("X-Workflow-Admin-Token") == "test" else (False, {"ok": False}, 401)
        return photo_request(method, path, self.headers if headers is None else headers,
                             payload, authorize, "https://app.test")

    def sample(self):
        return {"name": "../../photo.png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode()}

    def test_roundtrip_delete(self):
        body, status = self.call(payload=self.sample())
        self.assertEqual(status, 201)
        self.assertEqual(body["file"]["name"], "photo.png")
        route = "/photo-uploads/" + body["file"]["id"]
        body, status = self.call("GET", route)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"], self.sample()["data"])
        self.assertEqual(self.call("DELETE", route)[1], 200)
        self.assertEqual(self.call("GET", route)[1], 404)

    def test_unauthorized(self):
        self.assertEqual(self.call(payload=self.sample(), headers={})[1], 401)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_origin_and_traversal(self):
        self.assertEqual(self.call(payload=self.sample(), headers={**self.headers, "Origin": "https://evil.test"})[1], 403)
        self.assertEqual(self.call(payload=self.sample(), headers={**self.headers, "Origin": "http://127.0.0.1:3002"})[1], 201)
        self.assertEqual(self.call("GET", "/photo-uploads/../../server.py")[1], 404)

    def test_reject_bad_input(self):
        for payload in [None, [], {"data":"!"}, {"data":""}]:
            self.assertEqual(self.call(payload=payload)[1], 400)

    def test_accepts_any_image_payload_and_optional_quota(self):
        svg = {"name": "image.svg", "mime_type": "image/svg+xml", "data": base64.b64encode(b"<svg></svg>").decode()}
        body, status = self.call(payload=svg)
        self.assertEqual(status, 201)
        self.assertEqual(body["file"]["mime_type"], "image/svg+xml")
        with patch.dict(os.environ, {"PHOTO_UPLOAD_QUOTA_BYTES":"1"}):
            self.assertEqual(self.call(payload=self.sample())[1], 413)

    def test_private_metadata(self):
        body, _ = self.call(payload=self.sample())
        self.assertNotIn("data", body)
        self.assertNotIn(self.temp.name, str(body))
        self.assertEqual(body["file"]["access"], "admin-only")


if __name__ == "__main__":
    unittest.main()
