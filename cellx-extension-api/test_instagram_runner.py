import unittest
from unittest.mock import patch
import instagram_runner as runner


class InstagramTests(unittest.TestCase):
    def test_preview_does_not_open_browser_or_take_lock(self):
        with patch.object(runner, "LOCK") as lock:
            result = runner.run({"commentText": "Changed by user"}, execute=False)
        lock.acquire.assert_not_called()
        self.assertFalse(result["output"]["executed"])
        self.assertEqual(result["output"]["public_comment"], "Changed by user")

    def test_limit_rejects_unbounded_runs(self):
        for settings in ({"minPosts": 0}, {"maxPosts": 9}, {"minPosts": 7, "maxPosts": 5}):
            with self.assertRaises(ValueError):
                runner.config(settings)

    def test_empty_comments_rejected(self):
        with self.assertRaises(ValueError):
            runner.run({"commentText": " "})

    def test_concurrent_run_is_rejected_before_browser(self):
        runner.LOCK.acquire()
        try:
            result = runner.run({}, execute=True)
        finally:
            runner.LOCK.release()
        self.assertFalse(result["ok"])
        self.assertIn("already running", result["message"])


if __name__ == "__main__":
    unittest.main()
