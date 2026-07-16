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


def http_error_bytes(status, payload):
    return HTTPError(
        "https://worker.example.test/upload",
        status,
        "worker error",
        hdrs=None,
        fp=io.BytesIO(payload),
    )


def deeply_nested_json(depth=1200):
    return b'{"value":' + (b"[" * depth) + b"0" + (b"]" * depth) + b"}"


class CmsConfigTests(unittest.TestCase):
    def test_loads_json_then_applies_non_empty_environment_overrides(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "cms_config.json"
            path.write_text(
                json.dumps(
                    {
                        "r2_worker_url": "https://file.example.test/",
                        "r2_public_base_url": "https://file-cdn.example.test/gallery/",
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
                    "R2_PUBLIC_BASE_URL": "https://ENV-CDN.example.test:443/gallery/",
                    "R2_UPLOAD_TOKEN": "env-secret",
                    "R2_REQUEST_TIMEOUT_SECONDS": "4.5",
                    "R2_MAX_UPLOAD_BYTES": "4321",
                },
            )

        self.assertEqual(config.r2_worker_url, "https://env.example.test/base")
        self.assertEqual(
            config.r2_public_base_url, "https://env-cdn.example.test/gallery"
        )
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
                        "r2_public_base_url": "https://file-cdn.example.test/base",
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
                    "R2_PUBLIC_BASE_URL": "",
                    "R2_UPLOAD_TOKEN": "",
                    "R2_REQUEST_TIMEOUT_SECONDS": "",
                    "R2_MAX_UPLOAD_BYTES": "  ",
                },
            )

        self.assertEqual(config.r2_worker_url, "https://file.example.test")
        self.assertEqual(
            config.r2_public_base_url, "https://file-cdn.example.test/base"
        )
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
        self.assertEqual(config.r2_public_base_url, "")
        self.assertEqual(config.request_timeout_seconds, 30.0)
        self.assertEqual(config.max_upload_bytes, 15 * 1024 * 1024)

    def test_load_rejects_unsafe_token_without_echoing_it(self):
        unsafe_token = "secret\r\nX-Leaked-Header: yes"
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "missing.json"

            with self.assertRaises(ValueError) as context:
                CmsConfig.load(path, {"R2_UPLOAD_TOKEN": unsafe_token})

        self.assertEqual(
            str(context.exception),
            "R2 upload token must contain only visible ASCII characters",
        )
        self.assertNotIn(unsafe_token, str(context.exception))

    def test_public_base_is_required_for_configured_media_operations(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "cms_config.json"
            path.write_text(
                json.dumps(
                    {
                        "r2_worker_url": "https://worker.example.test",
                        "r2_upload_token": "test-token",
                    }
                ),
                encoding="utf-8",
            )

            config = CmsConfig.load(path, {})

        self.assertFalse(config.configured)

    def test_public_base_rejects_untrusted_url_shapes(self):
        invalid_values = (
            "http://cdn.example.test",
            "https://user:pass@cdn.example.test",
            "https://cdn.example.test/base?query=1",
            "https://cdn.example.test/base#fragment",
            "https://cdn.example.test:bad-port",
            "//cdn.example.test/base",
            "https://cdn.example.test/\u202ehidden",
            "https://cdn.example.test/base/./child",
            "https://cdn.example.test/base/../child",
            "https://cdn.example.test/base/%2e/child",
            "https://cdn.example.test/base/%2E%2E/child",
            "https://cdn.example.test\\outside",
            "https://cdn.example.test/base\\child",
            "https://cdn.example.test/base\\..\\secret",
        )
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "missing.json"
            for value in invalid_values:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError) as context:
                        CmsConfig.load(path, {"R2_PUBLIC_BASE_URL": value})
                    self.assertEqual(
                        str(context.exception),
                        "r2_public_base_url must be a valid HTTPS URL",
                    )

    def test_public_base_canonicalizes_idna_ipv4_and_ipv6_hosts(self):
        cases = (
            (
                "https://BÜCHER.example:443/gallery/",
                "https://xn--bcher-kva.example/gallery",
            ),
            ("https://127.0.0.1:443/gallery/", "https://127.0.0.1/gallery"),
            (
                "https://[2001:DB8::1]:443/gallery/",
                "https://[2001:db8::1]/gallery",
            ),
        )
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "missing.json"
            for value, expected in cases:
                with self.subTest(value=value):
                    config = CmsConfig.load(
                        path,
                        {
                            "R2_WORKER_URL": "https://worker.example.test",
                            "R2_PUBLIC_BASE_URL": value,
                            "R2_UPLOAD_TOKEN": "test-token",
                        },
                    )
                    self.assertEqual(config.r2_public_base_url, expected)
                    self.assertTrue(config.configured)

    def test_public_base_rejects_percent_escapes_anywhere_in_hostname(self):
        invalid_values = (
            "https://%63dn.example.test/gallery",
            "https://cd%6e.example.test/gallery",
            "https://cdn.example%2etest/gallery",
        )
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "missing.json"
            for value in invalid_values:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError) as context:
                        CmsConfig.load(path, {"R2_PUBLIC_BASE_URL": value})
                    self.assertEqual(
                        str(context.exception),
                        "r2_public_base_url must be a valid HTTPS URL",
                    )

    def test_public_base_rejects_noncanonical_numeric_ipv4_hosts(self):
        invalid_values = (
            "https://127.1/gallery",
            "https://0x7f000001/gallery",
        )
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "missing.json"
            for value in invalid_values:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError) as context:
                        CmsConfig.load(path, {"R2_PUBLIC_BASE_URL": value})
                    self.assertEqual(
                        str(context.exception),
                        "r2_public_base_url must be a valid HTTPS URL",
                    )

    def test_public_base_preserves_standard_ipv4_and_dns_labels_with_digits(self):
        cases = (
            ("https://127.0.0.1/gallery/", "https://127.0.0.1/gallery"),
            (
                "https://cdn2.example.test:443/gallery/",
                "https://cdn2.example.test/gallery",
            ),
        )
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "missing.json"
            for value, expected in cases:
                with self.subTest(value=value):
                    config = CmsConfig.load(
                        path,
                        {
                            "R2_WORKER_URL": "https://worker.example.test",
                            "R2_PUBLIC_BASE_URL": value,
                            "R2_UPLOAD_TOKEN": "test-token",
                        },
                    )
                    self.assertEqual(config.r2_public_base_url, expected)
                    self.assertTrue(config.configured)

    def test_non_finite_timeout_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "missing.json"
            for value in ("NaN", "Infinity", "-Infinity"):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError) as context:
                        CmsConfig.load(
                            path,
                            {"R2_REQUEST_TIMEOUT_SECONDS": value},
                        )
                    self.assertEqual(
                        str(context.exception),
                        "request_timeout_seconds must be a positive number",
                    )

    def test_non_finite_max_upload_values_are_rejected_as_value_errors(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "cms_config.json"
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(value=value):
                    path.write_text(
                        json.dumps({"max_upload_bytes": value}),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError) as context:
                        CmsConfig.load(path, {})
                    self.assertEqual(
                        str(context.exception),
                        "max_upload_bytes must be a positive integer",
                    )


class R2ClientTests(unittest.TestCase):
    def config(self, **overrides):
        values = {
            "r2_worker_url": "https://worker.example.test/base",
            "r2_public_base_url": "https://cdn.example.test/base",
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

    def test_client_rejects_unsafe_tokens_before_constructing_a_request(self):
        unsafe_tokens = (
            "line\r\nbreak",
            "control\x01byte",
            "unicode-\u5bc6\u94a5",
            "contains space",
        )
        for unsafe_token in unsafe_tokens:
            with self.subTest(token=repr(unsafe_token)):
                config = self.config(r2_upload_token=unsafe_token)
                opener = FakeOpener()

                with self.assertRaises(ValueError) as context:
                    R2Client(config, opener=opener)

                self.assertEqual(
                    str(context.exception),
                    "R2 upload token must contain only visible ASCII characters",
                )
                self.assertNotIn(unsafe_token, str(context.exception))
                self.assertEqual(opener.calls, [])

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

    def test_http_401_message_with_del_uses_generic_auth_error(self):
        opener = FakeOpener(http_error(401, {"message": "hidden\u007ftext"}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "auth_failed",
            "R2 worker authentication failed",
            False,
        )

    def test_http_503_message_with_c1_control_uses_generic_unavailable_error(self):
        opener = FakeOpener(http_error(503, {"message": "hidden\u0085text"}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "service_unavailable",
            "R2 worker is temporarily unavailable",
            True,
        )

    def test_http_401_message_with_bidi_control_uses_generic_auth_error(self):
        opener = FakeOpener(http_error(401, {"message": "hidden\u202etext"}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "auth_failed",
            "R2 worker authentication failed",
            False,
        )

    def test_http_503_preserves_ordinary_unicode_worker_message(self):
        message = "R2 \u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528"
        opener = FakeOpener(http_error(503, {"message": message}))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "service_unavailable",
            message,
            True,
        )

    def test_deeply_nested_http_401_body_uses_generic_auth_error(self):
        opener = FakeOpener(http_error_bytes(401, deeply_nested_json()))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "auth_failed",
            "R2 worker authentication failed",
            False,
        )

    def test_deeply_nested_http_503_body_uses_generic_unavailable_error(self):
        opener = FakeOpener(http_error_bytes(503, deeply_nested_json()))
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.health()

        self.assert_r2_error(
            context,
            "service_unavailable",
            "R2 worker is temporarily unavailable",
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

    def test_deeply_nested_success_body_maps_to_invalid_response(self):
        opener = FakeOpener(FakeResponse(deeply_nested_json()))
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

    def test_upload_response_whitespace_only_key_maps_to_invalid_response(self):
        opener = FakeOpener(
            json_response({"ok": True, "key": "   ", "url": "https://cdn.test/a"})
        )
        client = R2Client(self.config(), opener=opener)

        with self.assertRaises(R2Error) as context:
            client.upload(b"x", "image/jpeg", "portrait", "2026-07-16", "a.jpg")

        self.assert_r2_error(
            context,
            "invalid_response",
            "R2 worker upload response is missing key or url",
            False,
        )

    def test_upload_response_whitespace_only_url_maps_to_invalid_response(self):
        opener = FakeOpener(
            json_response({"ok": True, "key": "images/a.jpg", "url": "\t"})
        )
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
