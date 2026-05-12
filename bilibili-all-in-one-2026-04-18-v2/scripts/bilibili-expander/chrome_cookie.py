# -*- coding: utf-8 -*-
"""Chrome DevTools cookie bridge for Bilibili login state.

This module intentionally avoids Playwright/Selenium. It talks to an existing
Chrome DevTools port, reads the logged-in profile cookies, stores them in a
local runtime state file, and returns masked summaries for logs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = ROOT / ".runtime"
DEFAULT_COOKIE_STATE = DEFAULT_RUNTIME_DIR / "bilibili-cookie-state.json"
DEFAULT_ENV_FILE = ROOT / ".env.generated.ps1"
DEFAULT_LOGIN_URL = "https://passport.bilibili.com/login?gourl=https%3A%2F%2Fwww.bilibili.com%2F"
DEFAULT_CDP_URLS = ("http://127.0.0.1:9222", "http://127.0.0.1:9223", "http://localhost:9222", "http://localhost:9223")
IMPORTANT_COOKIE_NAMES = (
    "SESSDATA",
    "bili_jct",
    "DedeUserID",
    "DedeUserID__ckMd5",
    "sid",
    "buvid3",
    "buvid4",
    "buvid_fp",
    "b_nut",
    "CURRENT_FNVAL",
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def mask_secret(value: str, *, keep: int = 3) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}<{len(value)}>"


def mask_cookie_header(cookie: str) -> str:
    parts = []
    for item in cookie.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            parts.append(mask_secret(item))
            continue
        name, value = item.split("=", 1)
        parts.append(f"{name}={mask_secret(value)}")
    return "; ".join(parts)


def parse_cookie_header(cookie: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in cookie.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        parsed[name.strip()] = value.strip()
    return parsed


def cookie_value(cookie: str, name: str) -> str:
    return parse_cookie_header(cookie).get(name, "")


def normalize_cdp_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        raise ValueError("empty CDP URL")
    if not value.startswith(("http://", "https://")):
        value = "http://" + value
    return value


def candidate_cdp_urls(explicit: list[str] | None = None) -> list[str]:
    urls: list[str] = []
    for value in explicit or []:
        if value:
            urls.append(normalize_cdp_url(value))
    for name in ("BILIBILI_CDP_URL", "CHROME_DIDY_CDP_URL", "CHROME_CDP_URL"):
        value = os.environ.get(name)
        if value:
            urls.append(normalize_cdp_url(value))
    urls.extend(DEFAULT_CDP_URLS)
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            unique.append(url)
            seen.add(url)
    return unique


def request_json(url: str, *, method: str = "GET", timeout: int = 5) -> Any:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def request_text(url: str, *, method: str = "GET", timeout: int = 5) -> str:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def cdp_version(cdp_url: str) -> dict[str, Any]:
    return request_json(f"{normalize_cdp_url(cdp_url)}/json/version", timeout=3)


def list_targets(cdp_url: str) -> list[dict[str, Any]]:
    data = request_json(f"{normalize_cdp_url(cdp_url)}/json/list", timeout=3)
    return data if isinstance(data, list) else []


def open_target(cdp_url: str, url: str = DEFAULT_LOGIN_URL) -> dict[str, Any]:
    base = normalize_cdp_url(cdp_url)
    encoded = urllib.parse.quote(url, safe=":/?&=%")
    endpoint = f"{base}/json/new?{encoded}"
    try:
        data = request_json(endpoint, method="PUT", timeout=5)
    except urllib.error.HTTPError as exc:
        if exc.code not in {404, 405}:
            raise
        data = request_json(endpoint, method="GET", timeout=5)
    return data if isinstance(data, dict) else {}


def find_or_open_bilibili_target(cdp_url: str, *, open_login: bool = True) -> dict[str, Any]:
    for target in list_targets(cdp_url):
        if target.get("type") != "page":
            continue
        target_url = str(target.get("url") or "")
        if "bilibili.com" in target_url or "passport.bilibili.com" in target_url:
            if target.get("webSocketDebuggerUrl"):
                return target
    if open_login:
        target = open_target(cdp_url)
        if target.get("webSocketDebuggerUrl"):
            return target
    for target in list_targets(cdp_url):
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
            return target
    raise RuntimeError(f"No Chrome page target with DevTools WebSocket found at {cdp_url}")


class CdpWebSocket:
    """Minimal text WebSocket client for local Chrome DevTools."""

    def __init__(self, websocket_url: str, timeout: int = 10) -> None:
        self.websocket_url = websocket_url
        self.timeout = timeout
        self.sock: socket.socket | ssl.SSLSocket | None = None
        self.next_id = 1

    def __enter__(self) -> "CdpWebSocket":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def connect(self) -> None:
        parsed = urllib.parse.urlparse(self.websocket_url)
        if parsed.scheme not in {"ws", "wss"}:
            raise ValueError(f"Unsupported WebSocket scheme: {parsed.scheme}")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        host = parsed.hostname or "127.0.0.1"
        raw = socket.create_connection((host, port), timeout=self.timeout)
        sock: socket.socket | ssl.SSLSocket
        if parsed.scheme == "wss":
            sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        else:
            sock = raw
        sock.settimeout(self.timeout)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"CDP WebSocket handshake failed: {response[:200]!r}")
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest())
        if expected not in response:
            raise RuntimeError("CDP WebSocket handshake failed: invalid accept header")
        self.sock = sock

    def close(self) -> None:
        if not self.sock:
            return
        try:
            self._send_frame(b"", opcode=0x8)
        except Exception:
            pass
        try:
            self.sock.close()
        finally:
            self.sock = None

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        self._send_json({"id": request_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            opcode, payload = self._recv_frame(timeout=max(1, int(deadline - time.monotonic())))
            if opcode not in {0x1, 0x2}:
                continue
            data = json.loads(payload.decode("utf-8", errors="replace"))
            if data.get("id") != request_id:
                continue
            if data.get("error"):
                raise RuntimeError(f"CDP {method} failed: {data['error']}")
            return data.get("result") or {}
        raise TimeoutError(f"Timed out waiting for CDP method {method}")

    def _send_json(self, value: dict[str, Any]) -> None:
        self._send_frame(json.dumps(value, separators=(",", ":")).encode("utf-8"), opcode=0x1)

    def _send_frame(self, payload: bytes, opcode: int) -> None:
        if not self.sock:
            raise RuntimeError("WebSocket is not connected")
        first = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = bytes([first, 0x80 | length])
        elif length < 65536:
            header = bytes([first, 0x80 | 126]) + length.to_bytes(2, "big")
        else:
            header = bytes([first, 0x80 | 127]) + length.to_bytes(8, "big")
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def _recv_frame(self, timeout: int | None = None) -> tuple[int, bytes]:
        if not self.sock:
            raise RuntimeError("WebSocket is not connected")
        old_timeout = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            header = self._recv_exact(2)
            first, second = header
            opcode = first & 0x0F
            length = second & 0x7F
            masked = bool(second & 0x80)
            if length == 126:
                length = int.from_bytes(self._recv_exact(2), "big")
            elif length == 127:
                length = int.from_bytes(self._recv_exact(8), "big")
            mask = self._recv_exact(4) if masked else b""
            payload = self._recv_exact(length) if length else b""
            if masked:
                payload = bytes(byte ^ mask[idx % 4] for idx, byte in enumerate(payload))
            if opcode == 0x9:
                self._send_frame(payload, opcode=0xA)
                return self._recv_frame(timeout=timeout)
            if opcode == 0x8:
                raise RuntimeError("CDP WebSocket closed")
            return opcode, payload
        finally:
            if timeout is not None:
                self.sock.settimeout(old_timeout)

    def _recv_exact(self, size: int) -> bytes:
        if not self.sock:
            raise RuntimeError("WebSocket is not connected")
        chunks = []
        remaining = size
        while remaining:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError("WebSocket connection ended unexpectedly")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


def bilibili_cookies_from_target(target: dict[str, Any]) -> list[dict[str, Any]]:
    websocket_url = target.get("webSocketDebuggerUrl")
    if not websocket_url:
        raise RuntimeError("Chrome target does not expose webSocketDebuggerUrl")
    with CdpWebSocket(websocket_url) as cdp:
        try:
            result = cdp.call("Network.getAllCookies")
            cookies = result.get("cookies") or []
        except Exception:
            result = cdp.call("Storage.getCookies")
            cookies = result.get("cookies") or []
    rows = []
    for item in cookies:
        domain = str(item.get("domain") or "")
        if "bilibili.com" not in domain:
            continue
        name = str(item.get("name") or "")
        value = str(item.get("value") or "")
        if not name or value == "":
            continue
        rows.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": item.get("path") or "/",
            "expires": item.get("expires"),
            "httpOnly": bool(item.get("httpOnly")),
            "secure": bool(item.get("secure")),
        })
    return rows


def cookies_to_header(cookies: list[dict[str, Any]]) -> str:
    by_name: dict[str, str] = {}
    for item in cookies:
        name = str(item.get("name") or "")
        value = str(item.get("value") or "")
        if name and value:
            by_name[name] = value
    ordered = []
    for name in IMPORTANT_COOKIE_NAMES:
        if name in by_name:
            ordered.append((name, by_name.pop(name)))
    ordered.extend(sorted(by_name.items()))
    return "; ".join(f"{name}={value}" for name, value in ordered)


def validate_cookie(cookie: str, *, timeout: int = 10) -> dict[str, Any]:
    if not cookie:
        return {"ok": False, "is_login": False, "message": "empty cookie"}
    req = urllib.request.Request(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json,text/plain,*/*",
            "Cookie": cookie,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return {"ok": False, "is_login": False, "message": str(exc)}
    payload = data.get("data") or {}
    is_login = bool(payload.get("isLogin"))
    return {
        "ok": data.get("code") == 0,
        "is_login": is_login,
        "mid": payload.get("mid"),
        "uname": payload.get("uname"),
        "vip": payload.get("vipStatus"),
        "message": data.get("message"),
    }


def state_payload(cookies: list[dict[str, Any]], *, cdp_url: str, target_url: str, validation: dict[str, Any]) -> dict[str, Any]:
    cookie = cookies_to_header(cookies)
    return {
        "schema": 1,
        "updated_at": now_iso(),
        "source": {
            "type": "chrome-devtools",
            "cdp_url": cdp_url,
            "target_url": target_url,
        },
        "validation": validation,
        "cookie": cookie,
        "masked_cookie": mask_cookie_header(cookie),
        "cookie_names": [item.get("name") for item in cookies if item.get("name")],
        "cookies": cookies,
    }


def save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(path: Path | None = None) -> dict[str, Any]:
    path = path or Path(os.environ.get("BILIBILI_COOKIE_STATE", str(DEFAULT_COOKIE_STATE)))
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_cookie_header(path: Path | None = None) -> str:
    env_cookie = os.environ.get("BILIBILI_COOKIE", "").strip()
    if env_cookie:
        return env_cookie
    state = load_state(path)
    return str(state.get("cookie") or "")


def write_env_file(env_file: Path, *, cookie: str, state_path: Path, cdp_url: str) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)

    def ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    lines = [
        "# Generated by bilibili-all-in-one cookie bridge. Do not commit.",
        f"$env:BILIBILI_COOKIE_STATE = {ps_quote(str(state_path))}",
        f"$env:BILIBILI_CDP_URL = {ps_quote(cdp_url)}",
        f"$env:BILIBILI_COOKIE = {ps_quote(cookie)}",
        "",
    ]
    env_file.write_text("\n".join(lines), encoding="utf-8")


def export_cookie_from_chrome(
    *,
    cdp_urls: list[str] | None = None,
    state_path: Path = DEFAULT_COOKIE_STATE,
    env_file: Path | None = DEFAULT_ENV_FILE,
    wait_login: int = 180,
    open_login: bool = True,
    require_login: bool = True,
) -> dict[str, Any]:
    last_error = None
    started = time.monotonic()
    deadline = started + max(0, wait_login)
    for cdp_url in candidate_cdp_urls(cdp_urls):
        try:
            cdp_version(cdp_url)
            target = find_or_open_bilibili_target(cdp_url, open_login=open_login)
        except Exception as exc:
            last_error = exc
            continue
        while True:
            cookies = bilibili_cookies_from_target(target)
            cookie = cookies_to_header(cookies)
            validation = validate_cookie(cookie) if cookie else {"ok": False, "is_login": False, "message": "no bilibili cookies"}
            if cookie and (validation.get("is_login") or not require_login or time.monotonic() >= deadline):
                payload = state_payload(cookies, cdp_url=cdp_url, target_url=str(target.get("url") or ""), validation=validation)
                save_state(state_path, payload)
                if env_file:
                    write_env_file(env_file, cookie=cookie, state_path=state_path, cdp_url=cdp_url)
                return {
                    "ok": bool(validation.get("is_login")) or not require_login,
                    "state": str(state_path),
                    "env_file": str(env_file) if env_file else None,
                    "cdp_url": cdp_url,
                    "target_url": target.get("url"),
                    "validation": validation,
                    "cookie_names": payload["cookie_names"],
                    "masked_cookie": payload["masked_cookie"],
                }
            if wait_login <= 0 or time.monotonic() >= deadline:
                return {
                    "ok": False,
                    "state": str(state_path),
                    "cdp_url": cdp_url,
                    "target_url": target.get("url"),
                    "validation": validation,
                    "cookie_names": [item.get("name") for item in cookies],
                    "masked_cookie": mask_cookie_header(cookie),
                    "message": "login not detected before timeout",
                }
            time.sleep(3)
    raise RuntimeError(f"No usable Chrome DevTools endpoint found. Last error: {last_error}")


def cookie_status(*, state_path: Path = DEFAULT_COOKIE_STATE, validate: bool = True) -> dict[str, Any]:
    state = load_state(state_path)
    env_cookie = os.environ.get("BILIBILI_COOKIE", "").strip()
    cookie = env_cookie or str(state.get("cookie") or "")
    validation = validate_cookie(cookie) if validate and cookie else None
    return {
        "has_cookie": bool(cookie),
        "source": "env:BILIBILI_COOKIE" if env_cookie else str(state_path),
        "state_exists": state_path.exists(),
        "updated_at": state.get("updated_at"),
        "validation": validation,
        "cookie_names": list(parse_cookie_header(cookie).keys()),
        "masked_cookie": mask_cookie_header(cookie),
    }


def find_chrome(chrome_path: str | None = None) -> str:
    if chrome_path and Path(chrome_path).exists():
        return chrome_path
    for name in ("chrome.exe", "chrome", "msedge.exe", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("Chrome or Edge executable not found")


def launch_chrome_for_login(
    *,
    port: int = 9222,
    profile_dir: Path | None = None,
    chrome_path: str | None = None,
    login_url: str = DEFAULT_LOGIN_URL,
) -> dict[str, Any]:
    profile_dir = profile_dir or Path(os.environ.get("BILIBILI_CHROME_PROFILE", str(DEFAULT_RUNTIME_DIR / "chrome-profile")))
    profile_dir.mkdir(parents=True, exist_ok=True)
    exe = find_chrome(chrome_path)
    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        login_url,
    ]
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {
        "chrome": exe,
        "port": port,
        "profile_dir": str(profile_dir),
        "cdp_url": f"http://127.0.0.1:{port}",
        "login_url": login_url,
    }
