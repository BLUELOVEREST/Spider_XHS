import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
import requests

from xhs_utils.karakeep_adapter import adapt_note_for_karakeep


class NoteRequest(BaseModel):
    url: HttpUrl


class DownloadRequest(BaseModel):
    url: HttpUrl
    mediaTypes: list[str] | None = None


app = FastAPI(title="Spider_XHS HTTP Wrapper")
_pc_api = None


def get_pc_api():
    global _pc_api
    if _pc_api is None:
        from apis.xhs_pc_apis import XHS_Apis

        _pc_api = XHS_Apis()
    return _pc_api


def load_cookie() -> str:
    cookie = os.getenv("XHS_COOKIE", "").strip()
    if cookie:
        return cookie

    cookie_file = os.getenv("XHS_COOKIE_FILE", "").strip()
    if cookie_file:
        return Path(cookie_file).read_text(encoding="utf-8").strip()

    legacy_cookie = os.getenv("COOKIES", "").strip()
    if legacy_cookie:
        return legacy_cookie

    raise RuntimeError("Set XHS_COOKIE, XHS_COOKIE_FILE, or COOKIES before starting the service")


def include_raw_response() -> bool:
    return os.getenv("XHS_INCLUDE_RAW", "").strip().lower() in ("1", "true", "yes", "on")


def download_dir() -> Path:
    return Path(os.getenv("XHS_DOWNLOAD_DIR", "/downloads")).resolve()


def request_timeout() -> float:
    return float(os.getenv("XHS_REQUEST_TIMEOUT_SECONDS", "30"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _extract_feed_item(note_response: Any) -> Any:
    if not isinstance(note_response, dict):
        return note_response

    data = note_response.get("data")
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list) and items:
            return items[0]

    return note_response


def _response(success: bool, msg: str, note: Any = None, error_code: str | None = None) -> dict[str, Any]:
    return {
        "success": success,
        "errorCode": error_code,
        "msg": msg,
        "note": note,
    }


def _validate_note_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if host == "www.xiaohongshu.com" or host.endswith(".xiaohongshu.com"):
        if path.startswith("/explore/") or path.startswith("/discovery/item/"):
            note_id = path.split("/")[-1]
            if note_id:
                return None
    return "INVALID_URL"


def _is_xhs_shortlink(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == "xhslink.com" or host.endswith(".xhslink.com") or host == "xhslink.cn" or host.endswith(".xhslink.cn")


def _extract_original_url(url: str) -> str:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("originalUrl")
    if values and values[0]:
        return values[0]
    return url


def resolve_input_url(input_url: str) -> str:
    if not _is_xhs_shortlink(input_url):
        return input_url

    headers = {
        "user-agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
        ),
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = requests.get(input_url, headers=headers, allow_redirects=True, timeout=request_timeout())
    response.raise_for_status()
    return _extract_original_url(response.url)


def _classify_upstream_failure(msg: str) -> str:
    lowered = msg.lower()
    if "cookie" in lowered or "login" in lowered or "登录" in msg:
        return "AUTH_REQUIRED"
    if "不存在" in msg or "无权限" in msg or "删除" in msg:
        return "NOTE_UNAVAILABLE"
    return "UPSTREAM_ERROR"


def _adapt_feed_item(raw_note: Any, input_url: str) -> Any:
    if not isinstance(raw_note, dict):
        return None

    raw_note.setdefault("url", input_url)
    return adapt_note_for_karakeep(raw_note, include_raw=include_raw_response())


def _parse_note(input_url: str) -> tuple[dict[str, Any] | None, str, str | None]:
    input_url = resolve_input_url(input_url)
    error_code = _validate_note_url(input_url)
    if error_code:
        return None, "Invalid Xiaohongshu note URL", error_code

    cookie = load_cookie()
    success, msg, note_response = get_pc_api().get_note_info(input_url, cookie)
    if not success:
        return None, str(msg), _classify_upstream_failure(str(msg))

    raw_note = _extract_feed_item(note_response)
    note = _adapt_feed_item(raw_note, input_url)
    if note is None:
        return None, "Failed to parse Xiaohongshu note", "PARSE_FAILED"
    return note, str(msg), None


@app.post("/api/xhs/note")
def get_note(req: NoteRequest) -> dict[str, Any]:
    try:
        input_url = str(req.url)
        note, msg, error_code = _parse_note(input_url)
        if error_code:
            return _response(False, msg, error_code=error_code)
        return _response(True, msg, note=note)
    except RuntimeError as exc:
        return _response(False, str(exc), error_code="AUTH_REQUIRED")
    except Exception as exc:
        return _response(False, f"{type(exc).__name__}: {exc}", error_code="UPSTREAM_ERROR")


def _extension_for_asset(asset: dict[str, Any]) -> str:
    mime_type = str(asset.get("mimeType") or "").lower()
    url = str(asset.get("url") or "").lower().split("?", 1)[0]
    if mime_type == "image/png" or url.endswith(".png"):
        return ".png"
    if mime_type == "image/webp" or url.endswith(".webp"):
        return ".webp"
    if mime_type == "video/mp4" or url.endswith(".mp4"):
        return ".mp4"
    if str(asset.get("kind")) == "video":
        return ".mp4"
    return ".jpg"


def _file_name_for_asset(asset: dict[str, Any]) -> str:
    kind = str(asset.get("kind") or "file")
    role = str(asset.get("role") or "content")
    index = int(asset.get("index") or 0)
    extension = _extension_for_asset(asset)
    if kind == "image" and role == "cover":
        return f"cover{extension}"
    if kind == "video" and role == "content":
        return f"video{extension}"
    return f"{kind}_{index}{extension}"


def download_media_url(url: str, path: Path) -> None:
    timeout = float(os.getenv("XHS_DOWNLOAD_TIMEOUT_SECONDS", "120"))
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    path.write_bytes(response.content)


def _selected_assets(note: dict[str, Any], media_types: list[str] | None) -> list[dict[str, Any]]:
    allowed = set(media_types or ["image", "video"])
    assets = note.get("assets")
    if not isinstance(assets, list):
        return []
    return [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("kind") or "") in allowed
        and str(asset.get("url") or "").startswith("http")
    ]


@app.post("/api/xhs/download")
def download_note(req: DownloadRequest) -> dict[str, Any]:
    try:
        note, msg, error_code = _parse_note(str(req.url))
        if error_code:
            return {**_response(False, msg, error_code=error_code), "files": []}

        assert note is not None
        assets = _selected_assets(note, req.mediaTypes)
        if not assets:
            requested = set(req.mediaTypes or ["image", "video"])
            if requested == {"video"} and note.get("type") != "video":
                return {**_response(False, "Xiaohongshu note is not a video note", note=note, error_code="NO_VIDEO"), "files": []}
            return {**_response(False, "No downloadable media found", note=note, error_code="NO_MEDIA"), "files": []}

        note_id = str(note.get("id") or "unknown")
        target_dir = download_dir() / note_id
        target_dir.mkdir(parents=True, exist_ok=True)

        files = []
        for asset in assets:
            file_name = _file_name_for_asset(asset)
            path = target_dir / file_name
            download_media_url(str(asset["url"]), path)
            files.append(
                {
                    "kind": asset.get("kind"),
                    "path": str(path),
                    "name": file_name,
                    "mimeType": asset.get("mimeType"),
                    "role": asset.get("role"),
                    "index": asset.get("index"),
                    "sizeBytes": path.stat().st_size,
                }
            )

        return {
            "success": True,
            "errorCode": None,
            "msg": msg,
            "note": {
                "id": note.get("id"),
                "url": note.get("url"),
                "type": note.get("type"),
                "title": note.get("title"),
            },
            "files": files,
        }
    except RuntimeError as exc:
        return {**_response(False, str(exc), error_code="AUTH_REQUIRED"), "files": []}
    except Exception as exc:
        return {**_response(False, f"{type(exc).__name__}: {exc}", error_code="DOWNLOAD_FAILED"), "files": []}
