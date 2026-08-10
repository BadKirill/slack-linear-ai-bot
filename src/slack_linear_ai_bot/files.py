"""Slack image discovery, validation, and private-file download."""

from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


def is_image_file(file_obj: dict[str, Any]) -> bool:
    mimetype = (file_obj.get("mimetype") or "").lower()
    if mimetype.startswith("image/"):
        return True
    return (file_obj.get("filetype") or "").lower() in {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "heic"}


def sniff_raster_image_mime(data: bytes) -> str | None:
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def is_probably_html_page(data: bytes) -> bool:
    sample = data[:4096].lstrip()
    if not sample:
        return False
    lower = sample[:2000].lower()
    return lower.startswith((b"<!doctype html", b"<html")) or bool(
        sample[:1] == b"<" and (b"<html" in lower[:200] or b"<head" in lower[:400])
    )


def image_mime_for_slack_download(content_type: str, data: bytes) -> str | None:
    if is_probably_html_page(data):
        return None
    sniffed = sniff_raster_image_mime(data)
    if sniffed:
        return sniffed
    normalized = (content_type or "").split(";")[0].strip().lower()
    return normalized if normalized.startswith("image/") and "svg" not in normalized else None


def count_thread_images(messages: list[dict[str, Any]]) -> int:
    return sum(
        1
        for message in messages
        for file_obj in message.get("files") or []
        if isinstance(file_obj, dict) and is_image_file(file_obj)
    )


def build_thread_images_block(messages: list[dict[str, Any]], max_files: int) -> tuple[str, list[str]]:
    lines: list[str] = []
    private_urls: list[str] = []
    included = 0
    for message in messages:
        for file_obj in message.get("files") or []:
            if not isinstance(file_obj, dict) or not is_image_file(file_obj) or included >= max_files:
                continue
            name = (file_obj.get("name") or file_obj.get("title") or "image").strip()
            permalink = (file_obj.get("permalink") or "").strip()
            private_url = (file_obj.get("url_private") or "").strip()
            lines.append(f"- [{name}]({permalink})" if permalink else f"- {name}")
            included += 1
            if private_url:
                private_urls.append(private_url)
    if not lines:
        return "", []
    total = count_thread_images(messages)
    header = "[Thread images]"
    if total > included:
        header += f" ({included} of {total} included)"
    return header + "\n" + "\n".join(lines), private_urls


def collect_image_file_urls(messages: list[dict[str, Any]], max_files: int) -> list[str]:
    urls: list[str] = []
    for message in messages:
        for file_obj in message.get("files") or []:
            if not isinstance(file_obj, dict) or not is_image_file(file_obj):
                continue
            private_url = (file_obj.get("url_private") or "").strip()
            if private_url:
                urls.append(private_url)
            if len(urls) >= max_files:
                return urls
    return urls


async def download_slack_file_as_data_url(
    url_private: str,
    token: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
) -> str:
    if not url_private or not token:
        return ""
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout, headers={"Authorization": f"Bearer {token}"}) as session,
            session.get(url_private) as response,
        ):
            if response.status != 200:
                return ""
            data = await response.read()
            if not data or len(data) > max_bytes:
                return ""
            mime = image_mime_for_slack_download(response.headers.get("Content-Type", ""), data)
            if not mime:
                logger.warning("Slack private file did not contain a supported raster image")
                return ""
            return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    except (TimeoutError, aiohttp.ClientError) as exc:
        logger.warning("Slack private file download failed: %s", exc)
        return ""
