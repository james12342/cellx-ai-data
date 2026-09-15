import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import promo_videos as promo
import runway_videos as runway


class RunwayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"PROMO_VIDEO_DIR": str(self.root), "RUNWAYML_API_SECRET": "test-only", "RUNWAY_API_KEY": ""})
        self.env.start()
        runway.ACTIVE.clear()
        self.payload = {"request_id": "a" * 40, "photo_ids": ["b" * 40], "confirm_paid": True,
                        "approved_credits": 416, "options": {"mode": "runway", "duration_seconds": 10,
                        "aspect_ratio": "9:16", "product_info": "Blue ceramic cup", "style": "studio"}}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()
        runway.ACTIVE.clear()

    def job(self, **kwargs):
        job = {"ok": True, "id": "a" * 40, "provider": "runway", "status": "rendering", "task_id": "task-123",
               "options": runway.validate(self.payload), "created_at": 1}
        job.update(kwargs)
        promo.write_status(self.root, job)
        return job

    def test_validation(self):
        for duration in [3, 16, 4.5, True, "10", float("nan"), float("inf")]:
            self.payload["options"]["duration_seconds"] = duration
            self.assertEqual(runway.start(self.root, self.payload)[1], 400)
        self.assertEqual(runway.provider_info()["runway_configured"], True)
        self.assertNotIn("test-only", json.dumps(runway.provider_info()))

    def test_missing_key_and_payment(self):
        with patch.dict(os.environ, {"RUNWAYML_API_SECRET": ""}):
            self.assertEqual(promo.video_request("POST", "/promo-videos", self.payload)[1], 503)
        self.payload["confirm_paid"] = False
        with patch.object(runway, "product_ad_task") as api:
            self.assertEqual(runway.start(self.root, self.payload)[1], 400)
            api.assert_not_called()

    def test_photo_limit_before_submission(self):
        self.payload['photo_ids'] = ['b' * 40] * 11
        with patch.object(runway, 'product_ad_task') as api:
            result, status = runway.start(self.root, self.payload)
            self.assertEqual(status, 400)
            self.assertIn('at most 10', result['message'])
            api.assert_not_called()
            self.assertEqual(list(self.root.glob('*.json')), [])
        self.payload['photo_ids'] = ['b' * 40] * 10
        runway.validate(self.payload)

    def test_rejected_submission_is_not_uncertain(self):
        class BadRequestError(Exception):
            status_code = 400
        job = self.job(status='submitting')
        with patch.object(runway, 'product_ad_task', side_effect=BadRequestError('private provider payload')):
            runway.submit(self.root, job, [])
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['provider_http_status'], 400)
        self.assertNotIn('private provider payload', job['message'])

    def test_idempotence_and_single_job(self):
        self.job()
        with patch.object(runway, "product_ad_task") as api:
            self.assertEqual(runway.start(self.root, self.payload)[1], 200)
            self.payload["request_id"] = "c" * 40
            self.assertEqual(runway.start(self.root, self.payload)[1], 409)
            api.assert_not_called()

    def test_submit_success_and_unknown_outcome(self):
        job = self.job(status="submitting")
        def downloaded(url, path):
            path.write_bytes(b"fixture video")
        with patch.object(runway, "product_ad_task", return_value={"id": "task-ok", "output": ["https://example.cloudfront.net/video.mp4"]}) as api, patch.object(runway, "download", side_effect=downloaded):
            runway.submit(self.root, job, [{"uri": "data:image/png;base64,fixture"}])
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["task_id"], "task-ok")
            self.assertEqual(api.call_args.args[0]["aspect_ratio"], "9:16")
        with patch.object(runway, "product_ad_task", side_effect=TimeoutError):
            runway.submit(self.root, job, [])
            self.assertEqual(job["status"], "needs_review")

    def test_submit_sdk_and_task_failures(self):
        job = self.job(status="submitting")
        with patch.object(runway, "product_ad_task", side_effect=RuntimeError("Runway Python SDK is not installed.")):
            runway.submit(self.root, job, [])
            self.assertEqual(job["status"], "failed")
            self.assertIn("Install the runwayml package", job["message"])
        class TaskFailedError(Exception):
            def __init__(self):
                super().__init__("failed")
                self.task_details = {"failure": "moderated"}
        with patch.object(runway, "product_ad_task", side_effect=TaskFailedError()):
            runway.submit(self.root, job, [])
            self.assertEqual(job["status"], "failed")
            self.assertIn("moderated", job["message"])

    def test_restart_and_delete_guard(self):
        job = self.job(status="submitting")
        self.assertEqual(runway.poll(self.root, job)["status"], "needs_review")
        self.job()
        self.assertEqual(promo.video_request("DELETE", "/promo-videos/" + job["id"], {})[1], 409)

    def test_complete_and_failure(self):
        job = self.job()
        (self.root / (job["id"] + ".mp4")).write_bytes(b"fixture video")
        job.update(status="completed")
        promo.write_status(self.root, job)
        self.assertEqual(promo.video_request("GET", "/promo-videos/" + job["id"] + "/file", {})[1], 200)

    def test_output_url_safety(self):
        for url in ["http://cdn.cloudfront.net/v", "https://localhost/v", "https://cloudfront.net.attacker.com/v", "https://x.cloudfront.net:123/v", "https://a:b@x.cloudfront.net/v"]:
            with self.assertRaises(ValueError):
                runway.download(url, self.root / "test.mp4")
        with patch.object(runway.socket, "getaddrinfo", return_value=[(0, 0, 0, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError):
                runway.download("https://x.cloudfront.net/v", self.root / "test.mp4")


if __name__ == "__main__":
    unittest.main()
