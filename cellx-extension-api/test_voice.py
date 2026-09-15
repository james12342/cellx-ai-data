import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location("cellx_voice_server", Path(__file__).with_name("server.py"))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class VoiceTests(unittest.TestCase):
    def test_missing_key_does_not_call_provider(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(server, "urlopen") as call:
            self.assertEqual(server.ai_realtime_session({})[1], 400)
            call.assert_not_called()

    def test_session_only_returns_ephemeral_key(self):
        fake = io.BytesIO(json.dumps({"value": "ephemeral-test", "expires_at": 123, "session": {"internal": True}}).encode())
        with patch.dict(os.environ, {"OPENAI_API_KEY": "standard-test"}), patch.object(server, "urlopen", return_value=fake) as call:
            body, status = server.ai_realtime_session({"model": "untrusted", "instructions": "untrusted"})
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"ok", "value", "expires_at"})
        config = json.loads(call.call_args.args[0].data)["session"]
        self.assertNotEqual(config["model"], "untrusted")
        self.assertEqual({tool["name"] for tool in config["tools"]}, {"get_current_workflow", "build_workflow", "apply_workflow_draft"})

    def test_errors_do_not_leak_provider_response(self):
        error = HTTPError("url", 401, "bad", {}, io.BytesIO(b"sensitive provider detail"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch.object(server, "urlopen", side_effect=error):
            body, status = server.ai_realtime_session({})
        self.assertEqual(status, 502)
        self.assertNotIn("sensitive", json.dumps(body))

    def test_local_auth_requires_same_origin(self):
        handler = SimpleNamespace(headers={"Host": f"localhost:{server.PORT}", "Origin": f"http://localhost:{server.PORT}"}, client_address=("127.0.0.1", 123))
        with patch.object(server, "UI_DIR", "local-ui"), patch.object(server, "WORKFLOW_MANAGEMENT_TOKEN", "test-token"):
            self.assertTrue(server.ai_voice_auth(handler)[0])
            handler.headers["Origin"] = "https://foreign.example"
            self.assertFalse(server.ai_voice_auth(handler)[0])
            handler.headers["Origin"] = f"http://localhost:{server.PORT}"
            handler.headers["X-Forwarded-For"] = "remote"
            self.assertFalse(server.ai_voice_auth(handler)[0])

    def test_hosted_auth_requires_token(self):
        handler = SimpleNamespace(headers={"Host": "app.cellaidata.com"}, client_address=("127.0.0.1", 123))
        with patch.object(server, "UI_DIR", ""), patch.object(server, "WORKFLOW_MANAGEMENT_TOKEN", "test-token"):
            self.assertFalse(server.ai_voice_auth(handler)[0])
            handler.headers["X-Workflow-Admin-Token"] = "test-token"
            self.assertTrue(server.ai_voice_auth(handler)[0])

    def test_nested_secrets_are_removed(self):
        result = server.ai_workflow_context({"inputJson": '{"api_key":"private","limit":30}', "testResult": {"orders": []}})
        self.assertEqual(json.loads(result["inputJson"]), {"limit": 30})
        self.assertNotIn("testResult", result)


if __name__ == "__main__":
    unittest.main()
