import io
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError


TOOL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_DIR))

from r2_client import CmsConfig, R2Client, R2Error, R2Object  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self._body = io.BytesIO(payload)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return self._body.read(size)

    def close(self):
        self._body.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class FakeOpener:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def json_response(payload):
    return FakeResponse(json.dumps(payload).encode("utf-8"))


def http_error(status, payload=None):
    body = None if payload is None else io.BytesIO(json.dumps(payload).encode("utf-8"))
    return HTTPError(
        "https://worker.example.test/upload",
        status,
        "worker error",
        hdrs=None,
        fp=body,
    )


class CmsConfigTests(unittest.TestCase):
    def test_loads_json_then_applies_non_empty_environment_overrides(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "cms_config.json"
            path.write_text(
                json.dumps(
                    {
                        "r2_worker_url": "https://file.example.test/",
                        "r2_upload_token": "file-secret",
                        "request_timeout_seconds": 17,
                        "max_upload_bytes": 1234,
                    }
                ),
                encoding="utf-8",
            )

            config = CmsConfig.load(
                path,
                {
                    "R2_WORKER_URL": "https://env.example.test/base/",
                    "R2_UPLOAD_TOKEN": "env-secret",
                    "R2_REQUEST_TIMEOUT_SECONDS": "4.5",
                    "R2_MAX_UPLOAD_BYTES": "4321",
                },
            )

        self.assertEqual(config.r2_worker_url, "https://env.example.test/base")
        self.assertEqual(config.r2_upload_token, "env-secret")
        self.assertEqual(config.request_timeout_seconds, 4.5)
        self.assertEqual(config.max_upload_bytes, 4321)
        self.assertTrue(config.configured)
        self.assertNotIn("env-secret", repr(config))

    def test_empty_environment_values_do_not_replace_file_values(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "cms_config.json"
            path.write_text(
                json.dumps(
                    {
                        "r2_worker_url": "https://file.example.test",
                        "r2_upload_token": "file-secret",
                        "request_timeout_seconds": 9,
                        "max_upload_bytes": 2048,
                    }
                ),
                encoding="utf-8",
            )

            config = CmsConfig.load(
                path,
                {
                    "R2_WORKER_URL": " ",
                    "R2_UPLOAD_TOKEN": "",
                    "R2_REQUEST_TIMEOUT_SECONDS": "",
                    "R2_MAX_UPLOAD_BYTES": "  ",
                },
            )

        self.assertEqual(config.r2_worker_url, "https://file.example.test")
        self.assertEqual(config.r2_upload_token, "file-secret")
        self.assertEqual(config.request_timeout_seconds, 9.0)
        self.assertEqual(config.max_upload_bytes, 2048)

    def test_missing_file_url_and_token_produce_unconfigured_defaults(self):
        with tempfile.TemporaryDirectory() as tempdir:
            config = CmsConfig.load(
                Path(tempdir) / "missing.json",
                {},
            )

        self.assertFalse(config.configured)
        self.assertEqual(config.request_timeout_seconds, 30.0)
        self.assertEqual(config.max_upload_bytes, 15 * 1024 * 1024)


class R2ClientTests(unittest.TestCase):
    def config(self, **overrides):
        values = {
            "r2_worker_url": "https://worker.example.test/base",
            "r2_upload_token": "test-token",
            "request_timeout_seconds": 7.5,
            "max_upload_bytes": 1024,
        }
        values.update(overrides)
        return CmsConfig(**values)

    def assert_r2_error(self, context, code, message, retryable):
        error = context.exception
        self.assertEqual(error.code, code)
        self.assertEqual(error.message, message)
        self.assertEqual(error.retryable, retryable)
        self.assertNotIn("test-token", str(error))

    def test_health_sends_authenticated_get_and_decodes_json(self):
        response = json_response({"ok": True, "service": "r2"})
        opener = FakeOpener(response)
        client = R2Client(self.config(), opener=opener)

        result = client.health()

        self.assertEqual(result, {"ok": True, "service": "r2"})
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, "https://worker.example.test/base/health")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertIsNone(request.data)
        self.assertEqual(timeout, 7.5)
        self.assertEqual(response.read_sizes, [64 * 1024 + 1])

    def test_upload_sends_raw_bytes_and_returns_decoded_object(self):
        opener = FakeOpener(
            json_response(
                {
                    "ok": True,
                    "key": "images/portrait/2026-07-16/photo.jpg",
                    "url": "https://cdn.example.test/images/photo.jpg",
                }
            )
        )
        client = R2Client(self.config(), opener=opener)

        result = client.upload(
            b"image-bytes",
            "image/jpeg",
            "portrait work",
            "2026-07-16",
            "a/b \u7167\u7247.jpg",
        )

        self.assertEqual(
            result,
            R2Object(
                key="images/portrait/2026-07-16/photo.jpg",
                url="https://cdn.example.test/images/photo.jpg",
            ),
        )
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            "https://worker.example.test/base/upload?"
            "category=portrait+work&date=2026-07-16&"
            "filename=a%2Fb+%E7%85%A7%E7%89%87.jpg",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(request.get_header("Content-type"), "image/jpeg")
        self.assertEqual(request.data, b"image-bytes")
        self.assertEqual(timeout, 7.5)

    def test_delete_posts_json_and_returns_none(self):
        opener = FakeOpener(json_response({"ok": True}))
        client = R2Client(self.config(), opener=opener)

        result = client.delete("images/portrait/2026-07-16/photo.jpg")

        self.assertIsNone(result)
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, "https://worker.example.test/base/delete")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(
            request.data,
            b'{"key":"images/portrait/2026-07-16/photo.jpg"}',
        )
        self.assertEqual(timeout, 7.5)

    def test_http_401_maps_worker_message_to_non_retryable_auth_error(self):
        opener = FakeOpener(http_error(401, {"message": "Worker token rejected"}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "auth_failed",
            "Worker token rejected",
            False,
        )

    def test_http_401_without_json_body_uses_generic_safe_message(self):
        opener = FakeOpener(http_error(401))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "auth_failed",
            "R2 worker authentication failed",
            False,
        )

    def test_http_503_maps_worker_message_to_retryable_unavailable_error(self):
        opener = FakeOpener(http_error(503, {"message": "Worker is warming up"}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "service_unavailable",
            "Worker is warming up",
            True,
        )

    def test_timeout_maps_to_retryable_request_timeout(self):
        opener = FakeOpener(socket.timeout("secret low-level detail"))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "request_timeout",
            "R2 worker request timed out",
            True,
        )

    def test_url_error_maps_to_retryable_network_error(self):
        opener = FakeOpener(URLError("secret resolver detail"))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "network_error",
            "Unable to reach R2 worker",
            True,
        )

    def test_malformed_json_maps_to_non_retryable_invalid_response(self):
        opener = FakeOpener(FakeResponse(b"not-json"))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "invalid_response",
            "R2 worker returned invalid JSON",
            False,
        )

    def test_upload_response_missing_key_maps_to_invalid_response(self):
        opener = FakeOpener(json_response({"ok": True, "url": "https://cdn.test/a"}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.upload(b"x", "image/jpeg", "portrait", "2026-07-16", "a.jpg")

        self.assert_r2_error(
            context,
            "invalid_response",
            "R2 worker upload response is missing key or url",
            False,
        )

    def test_upload_response_missing_url_maps_to_invalid_response(self):
        opener = FakeOpener(json_response({"ok": True, "key": "images/a.jpg"}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.upload(b"x", "image/jpeg", "portrait", "2026-07-16", "a.jpg")

        self.assert_r2_error(
            context,
            "invalid_response",
            "R2 worker upload response is missing key or url",
            False,
        )

    def test_response_larger_than_64_kib_is_rejected_before_json_parsing(self):
        response = FakeResponse(b'{' + b'"padding":"' + b"x" * (64 * 1024) + b'"}')
        opener = FakeOpener(response)
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "invalid_response",
            "R2 worker response exceeds 64 KiB",
            False,
        )
        self.assertEqual(response.read_sizes, [64 * 1024 + 1])

    def test_worker_message_containing_token_is_not_exposed(self):
        opener = FakeOpener(http_error(401, {"message": "bad test-token"}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "auth_failed",
            "R2 worker authentication failed",
            False,
        )


if __name__ == "__main__":
    unittest.main()
