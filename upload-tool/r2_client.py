"""Configuration and authenticated HTTP client for the R2 upload Worker."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import json
import math
import socket
import unicodedata


DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
MAX_WORKER_MESSAGE_CHARACTERS = 1024
UNSAFE_TOKEN_MESSAGE = "R2 upload token must contain only visible ASCII characters"


def _non_empty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _validate_upload_token(token: str) -> None:
    if not isinstance(token, str) or any(
        ord(character) < 33 or ord(character) > 126 for character in token
    ):
        raise ValueError(UNSAFE_TOKEN_MESSAGE)


def _canonical_public_base_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    message = "r2_public_base_url must be a valid HTTPS URL"
    if any(
        character.isspace()
        or unicodedata.category(character) in ("Cc", "Cf")
        for character in raw
    ):
        raise ValueError(message)
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(message) from exc
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(message)
    canonical_host = hostname.lower()
    if ":" in canonical_host:
        canonical_host = "[{}]".format(canonical_host)
    netloc = canonical_host
    if port is not None and port != 443:
        netloc = "{}:{}".format(netloc, port)
    path = quote(
        unquote(parsed.path), safe="/:@-._~!$&'()*+,;="
    ).rstrip("/")
    return urlunsplit(("https", netloc, path, "", ""))


def _positive_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError("{} must be a positive number".format(name))
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("{} must be a positive number".format(name)) from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError("{} must be a positive number".format(name))
    return parsed


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError("{} must be a positive integer".format(name))
    try:
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("{} must be a positive integer".format(name)) from exc
    if parsed <= 0 or str(parsed) != str(value).strip():
        raise ValueError("{} must be a positive integer".format(name))
    return parsed


@dataclass(frozen=True)
class CmsConfig:
    r2_worker_url: str = ""
    r2_public_base_url: str = ""
    r2_upload_token: str = field(default="", repr=False)
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES

    @property
    def configured(self) -> bool:
        return bool(
            self.r2_worker_url
            and self.r2_public_base_url
            and self.r2_upload_token
        )

    @classmethod
    def load(cls, path: Any, environ: Mapping[str, str]) -> "CmsConfig":
        values: Dict[str, Any] = {
            "r2_worker_url": "",
            "r2_public_base_url": "",
            "r2_upload_token": "",
            "request_timeout_seconds": DEFAULT_REQUEST_TIMEOUT_SECONDS,
            "max_upload_bytes": DEFAULT_MAX_UPLOAD_BYTES,
        }
        config_path = Path(path)
        if config_path.exists():
            with config_path.open("r", encoding="utf-8-sig") as config_file:
                loaded = json.load(config_file)
            if not isinstance(loaded, dict):
                raise ValueError("CMS configuration must be a JSON object")
            for key in values:
                if key in loaded and loaded[key] is not None:
                    values[key] = loaded[key]

        environment_names = {
            "r2_worker_url": "R2_WORKER_URL",
            "r2_public_base_url": "R2_PUBLIC_BASE_URL",
            "r2_upload_token": "R2_UPLOAD_TOKEN",
            "request_timeout_seconds": "R2_REQUEST_TIMEOUT_SECONDS",
            "max_upload_bytes": "R2_MAX_UPLOAD_BYTES",
        }
        for key, environment_name in environment_names.items():
            environment_value = environ.get(environment_name)
            if _non_empty(environment_value):
                if key == "r2_upload_token":
                    values[key] = str(environment_value)
                else:
                    values[key] = str(environment_value).strip()

        worker_url = str(values["r2_worker_url"] or "").strip().rstrip("/")
        public_base_url = _canonical_public_base_url(
            values["r2_public_base_url"]
        )
        upload_token = str(values["r2_upload_token"] or "")
        if upload_token.strip() == "":
            upload_token = ""
        else:
            _validate_upload_token(upload_token)
        timeout = _positive_float(
            values["request_timeout_seconds"], "request_timeout_seconds"
        )
        max_upload_bytes = _positive_int(
            values["max_upload_bytes"], "max_upload_bytes"
        )
        return cls(
            r2_worker_url=worker_url,
            r2_public_base_url=public_base_url,
            r2_upload_token=upload_token,
            request_timeout_seconds=timeout,
            max_upload_bytes=max_upload_bytes,
        )


@dataclass(frozen=True)
class R2Object:
    key: str
    url: str


class R2Error(Exception):
    def __init__(self, code: str, message: str, retryable: bool):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class R2Client:
    def __init__(
        self,
        config: CmsConfig,
        opener: Optional[Callable[..., Any]] = None,
    ):
        _validate_upload_token(config.r2_upload_token)
        self.config = config
        self._opener = opener or urlopen

    def health(self) -> Dict[str, Any]:
        request = self._request_for("/health", method="GET")
        return self._open_json(request)

    def upload(
        self,
        content: bytes,
        content_type: str,
        category: str,
        date: str,
        filename: str,
    ) -> R2Object:
        query = urlencode(
            {
                "category": category,
                "date": date,
                "filename": filename,
            }
        )
        request = self._request_for(
            "/upload?{}".format(query),
            method="POST",
            body=content,
            content_type=content_type,
        )
        payload = self._open_json(request)
        key = payload.get("key")
        url = payload.get("url")
        if (
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(url, str)
            or not url.strip()
        ):
            raise R2Error(
                "invalid_response",
                "R2 worker upload response is missing key or url",
                False,
            )
        return R2Object(key=key, url=url)

    def delete(self, key: str) -> None:
        body = json.dumps(
            {"key": key}, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        request = self._request_for(
            "/delete",
            method="POST",
            body=body,
            content_type="application/json",
        )
        self._open_json(request)

    def _request_for(
        self,
        path: str,
        method: str,
        body: Optional[bytes] = None,
        content_type: Optional[str] = None,
    ) -> Request:
        headers = {
            "Authorization": "Bearer {}".format(self.config.r2_upload_token),
            "Accept": "application/json",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return Request(
            "{}{}".format(self.config.r2_worker_url, path),
            data=body,
            headers=headers,
            method=method,
        )

    def _open_json(self, request: Request) -> Dict[str, Any]:
        try:
            with self._opener(
                request, timeout=self.config.request_timeout_seconds
            ) as response:
                return self._decode_json(response)
        except HTTPError as error:
            self._raise_http_error(error)
        except (socket.timeout, TimeoutError):
            raise R2Error(
                "request_timeout", "R2 worker request timed out", True
            ) from None
        except URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise R2Error(
                    "request_timeout", "R2 worker request timed out", True
                ) from None
            raise R2Error(
                "network_error", "Unable to reach R2 worker", True
            ) from None
        except OSError:
            raise R2Error(
                "network_error", "Unable to reach R2 worker", True
            ) from None
        raise AssertionError("unreachable")

    def _decode_json(self, response: Any) -> Dict[str, Any]:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise R2Error(
                "invalid_response",
                "R2 worker response exceeds 64 KiB",
                False,
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            raise R2Error(
                "invalid_response",
                "R2 worker returned invalid JSON",
                False,
            ) from None
        if not isinstance(payload, dict):
            raise R2Error(
                "invalid_response",
                "R2 worker returned invalid JSON",
                False,
            )
        return payload

    def _raise_http_error(self, error: HTTPError) -> None:
        status = error.code
        if status in (401, 403):
            code = "auth_failed"
            fallback = "R2 worker authentication failed"
            retryable = False
        elif status == 429 or 500 <= status <= 599:
            code = "service_unavailable"
            fallback = "R2 worker is temporarily unavailable"
            retryable = True
        else:
            code = "network_error"
            fallback = "R2 worker request failed"
            retryable = True
        message = self._bounded_worker_message(error, fallback)
        raise R2Error(code, message, retryable) from None

    def _bounded_worker_message(self, error: HTTPError, fallback: str) -> str:
        if getattr(error, "fp", None) is None:
            return fallback
        try:
            raw = error.read(MAX_RESPONSE_BYTES + 1)
        except Exception:
            return fallback
        finally:
            try:
                error.close()
            except Exception:
                pass
        if len(raw) > MAX_RESPONSE_BYTES:
            return fallback
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            return fallback
        if not isinstance(payload, dict):
            return fallback
        message = payload.get("message")
        if not isinstance(message, str):
            return fallback
        message = message.strip()
        if not message or len(message) > MAX_WORKER_MESSAGE_CHARACTERS:
            return fallback
        if any(
            unicodedata.category(character) in ("Cc", "Cf")
            for character in message
        ):
            return fallback
        token = self.config.r2_upload_token
        if token and token in message:
            return fallback
        return message
