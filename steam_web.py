"""Local web UI server for the Steam Library Organizer.

Binds to 127.0.0.1 only. Everything it needs is read from the local Steam
install; the only optional network call is the official GetOwnedGames API when
the user supplies a key.
"""

from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
import mimetypes
import os
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from steam_library_core import (
    SCOPES,
    STEAM_DEFAULT,
    SteamError,
    SteamLibrary,
    detect_steam_root,
    validate_steam_root,
)

UI_DIR = Path(__file__).with_name("steam_ui")
DEFAULT_PORT = 8760
MODES = ("initial", "genre", "form", "developer", "publisher", "state", "recent", "playtime")
MAX_PLANS = 8
PLAN_TTL_SECONDS = 30 * 60
CSRF_TOKEN = secrets.token_urlsafe(32)


class Organizer:
    """Mutable server state: the library handle and the last generated plan."""

    def __init__(self, steam_root: str | Path | None = None) -> None:
        self.lock = threading.Lock()
        if steam_root is None:
            try:
                root = detect_steam_root()
            except SteamError:
                # Keep construction/import side-effect free on machines where
                # Steam is not installed. Scanning will report the missing
                # legacy path, while an eventual UI can call set_steam_root.
                root = Path(STEAM_DEFAULT)
        else:
            root = validate_steam_root(steam_root)
        self.library = SteamLibrary(root)
        self.plan: list[dict] = []
        self.selected: set[str] = set()
        self.plans: OrderedDict[str, dict] = OrderedDict()
        self.session_games: dict[int, dict] = {}

    @property
    def session_appids(self) -> set[int]:
        return set(self.session_games)

    def _clear_plans(self) -> None:
        self.plan = []
        self.selected = set()
        self.plans.clear()

    def set_steam_root(self, steam_root: str | Path) -> str:
        """Switch to a validated Steam install without retaining stale state."""
        root = validate_steam_root(steam_root)
        current = Path(self.library.root).resolve(strict=False)
        if os.path.normcase(str(root)) == os.path.normcase(str(current)):
            return str(root)

        replacement = SteamLibrary(root, self.library.language)
        # Resolve the account before committing the switch. A malformed
        # loginusers.vdf must leave the currently usable library untouched.
        replacement.resolve_account()
        self.library = replacement
        self.session_games = {}
        self._clear_plans()
        return str(root)

    @staticmethod
    def _stat_signature(path: Path) -> tuple[str, int | None, int | None]:
        """Return a stable, cheap signature without trusting a file's contents."""
        try:
            stat = path.stat()
        except OSError:
            return (str(path), None, None)
        return (str(path), stat.st_size, stat.st_mtime_ns)

    def _source_fingerprint(self) -> str:
        """Fingerprint every local source whose changes can make a plan stale."""
        lib = self.library
        paths: list[Path] = []
        try:
            root = Path(lib.root)
            paths.extend(
                [
                    root / "appcache" / "appinfo.vdf",
                    root / "steamapps" / "libraryfolders.vdf",
                    lib.config_dir / "localconfig.vdf",
                    lib.cloud_path(),
                ]
            )
            cache_dir = lib.config_dir / "librarycache"
            if cache_dir.is_dir():
                paths.extend(sorted(cache_dir.glob("*.json"), key=lambda path: path.name))
            for folder in lib.library_folders():
                manifest_dir = folder / "steamapps"
                paths.extend(
                    sorted(manifest_dir.glob("appmanifest_*.acf"), key=lambda path: path.name)
                )
        except (AttributeError, OSError, SteamError):
            # Test doubles and a partially installed Steam still receive a
            # deterministic fingerprint from whichever sources are available.
            pass
        signatures = [self._stat_signature(path) for path in paths]
        payload = json.dumps(signatures, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def state(self, refresh_metadata: bool = False) -> dict:
        lib = self.library
        try:
            appinfo = lib.appinfo(refresh=refresh_metadata)
        except Exception:
            appinfo = {}
        sources = lib.source_appids(self.session_appids)
        scoped = lib.scoped_appids(self.session_appids, self.session_games)
        catalog = lib.catalog(
            self.session_appids,
            "library",
            external_games=self.session_games,
        )
        named = sum(1 for item in catalog.values() if item["named"])
        try:
            running: bool | None = steam_running()
            steam_check_error = None
        except SteamError as exc:
            running = None
            steam_check_error = str(exc)
        return {
            "steam_root": str(lib.root),
            "account_id": lib.account_id,
            "steamid64": lib.steamid64,
            "steam_running": running,
            "steam_check_error": steam_check_error,
            "appinfo_entries": len(appinfo),
            "appinfo_error": lib.appinfo_error,
            "appinfo_stale": bool(lib.appinfo_error and appinfo),
            "default_scope": "library",
            "scopes": {
                "default": "library",
                "library": len(scoped["library"]),
                "games": len(scoped["games"]),
                "all": len(scoped["all"]),
                "unresolved": len(scoped["unresolved"]),
                "auxiliary": len(scoped["auxiliary"]),
                "local_only": len(scoped["local_only"]),
                "excluded": len(scoped["excluded"]),
            },
            "sources": {
                "local": len(sources["local"]),
                "cached": len(sources["cached"]),
                "installed": len(sources["installed"]),
                "session": len(sources["session"]),
            },
            "counts": {
                "candidates": len(catalog),
                "named": named,
                "local": len(sources["local"]),
                "cached": len(sources["cached"]),
                "installed": len(sources["installed"]),
                "library": len(scoped["library"]),
                "games": len(scoped["games"]),
                "all": len(scoped["all"]),
                "unresolved": len(scoped["unresolved"]),
                "auxiliary": len(scoped["auxiliary"]),
                "local_only": len(scoped["local_only"]),
                "excluded": len(scoped["excluded"]),
            },
            "collections": lib.current_collections(),
            "modes": MODES,
            "available_scopes": SCOPES,
            "session_owned": len(self.session_games),
            "csrf_token": CSRF_TOKEN,
        }

    def set_language(self, language: str) -> None:
        language = (language or "schinese").strip()
        if language == self.library.language:
            return
        replacement = SteamLibrary(self.library.root, language)
        replacement.resolve_account()
        self.library = replacement
        self._clear_plans()

    def set_owned_games(self, games: list[dict]) -> int:
        normalized: dict[int, dict] = {}
        for game in games:
            if not isinstance(game, dict):
                continue
            try:
                appid = int(game.get("appid"))
            except (TypeError, ValueError):
                continue
            if appid > 0:
                normalized[appid] = {
                    "appid": appid,
                    "name": str(game.get("name") or ""),
                    "playtime_forever": game.get("playtime_forever"),
                    "rtime_last_played": game.get("rtime_last_played"),
                }
        self.session_games = normalized
        self._clear_plans()
        return len(normalized)

    def make_plan(
        self,
        modes: list[str],
        developer_min: int,
        scope: str = "library",
    ) -> dict:
        if not isinstance(modes, list) or any(not isinstance(mode, str) for mode in modes):
            raise SteamError("分类方式格式错误")
        modes = list(dict.fromkeys(modes))
        unknown = [m for m in modes if m not in MODES]
        if unknown:
            raise SteamError("未知分类方式：" + ", ".join(unknown))
        if not modes:
            raise SteamError("请至少选择一种分类方式")
        if scope not in SCOPES:
            raise SteamError("未知条目范围：" + str(scope))
        if not 1 <= developer_min <= 100:
            raise SteamError("厂商最少游戏数必须在 1 到 100 之间")

        self.library.appinfo(refresh=True)
        if self.library.appinfo_error:
            raise SteamError(
                "Steam 元数据刷新失败，未生成可能过期的分类："
                + self.library.appinfo_error
            )
        source_fingerprint = self._source_fingerprint()
        catalog = self.library.catalog(
            self.session_appids,
            scope,
            external_games=self.session_games,
        )
        groups = self.library.build_groups(
            modes,
            developer_min=developer_min,
            scope=scope,
            catalog=catalog,
        )
        self.plan = copy.deepcopy(groups)
        self.selected = {group["id"] for group in groups}
        preview = []
        for group in groups:
            sample = [catalog.get(appid, {}).get("name", "") for appid in group["appids"][:6]]
            preview.append({**group, "appids": group["appids"], "sample": [s for s in sample if s]})

        unique_apps = {appid for group in groups for appid in group["appids"]}
        collections = self.library.current_collections()
        mode_stats = {}
        for mode in modes:
            mode_groups = [group for group in groups if group["mode"] == mode]
            mode_apps = {appid for group in mode_groups for appid in group["appids"]}
            mode_stats[mode] = {
                "groups": len(mode_groups),
                "unique_apps": len(mode_apps),
                "memberships": sum(group["count"] for group in mode_groups),
            }
        missing_metadata = sum(
            1 for item in catalog.values() if not item.get("named") or not item.get("form")
        )
        warnings = []
        if scope == "all":
            warnings.append("“全部本地记录”会包含工具、试玩、配置项和资料缺失条目。")
        if missing_metadata:
            warnings.append(f"有 {missing_metadata} 个条目的名称或类型资料不完整。")
        if self.session_games:
            warnings.append(
                f"已在本次会话纳入 API 返回的 {len(self.session_games)} 个条目；API Key 未保存。"
            )
        else:
            warnings.append("当前范围来自本地记录，可能包含家庭共享或历史缓存条目。")
        scope_details = self.library.scoped_appids(
            self.session_appids,
            self.session_games,
        )
        if scope != "all" and scope_details["local_only"]:
            warnings.append(
                f"已排除 {len(scope_details['local_only'])} 个仅见于 localconfig 的历史条目。"
            )
        if scope != "all" and scope_details["excluded"]:
            warnings.append(
                f"已排除 {len(scope_details['excluded'])} 个 Valve 测试条目。"
            )

        summary = {
            "groups": len(groups),
            "unique_apps": len(unique_apps),
            "memberships": sum(group["count"] for group in groups),
            "missing_metadata": missing_metadata,
            "mode_stats": mode_stats,
            "existing_managed": sum(1 for item in collections if item["ours"]),
            "manual_preserved": sum(1 for item in collections if not item["ours"]),
            "excluded_local_only": len(scope_details["local_only"]),
            "excluded_test_apps": len(scope_details["excluded"]),
            "warnings": warnings,
        }
        if source_fingerprint != self._source_fingerprint():
            raise SteamError("扫描期间 Steam 库数据发生变化，请重新生成预览")
        plan_id = secrets.token_urlsafe(18)
        self.plans[plan_id] = {
            "plan_id": plan_id,
            "account_id": self.library.account_id,
            "created": time.time(),
            "source_fingerprint": source_fingerprint,
            "scope": scope,
            "groups": copy.deepcopy(groups),
            "summary": copy.deepcopy(summary),
        }
        while len(self.plans) > MAX_PLANS:
            self.plans.popitem(last=False)
        return {
            "groups": preview,
            "total": len(groups),
            "plan_id": plan_id,
            "scope": scope,
            "summary": summary,
        }

    @staticmethod
    def _ensure_steam_stopped() -> None:
        if steam_running():
            raise SteamError("Steam 正在运行。请先从 Steam 菜单完全退出，再执行写入。")

    def apply(self, plan_id: str, selected_ids: list[str]) -> dict:
        # The process-wide lock covers every safety decision, not just the
        # eventual os.replace. Otherwise another process could write after this
        # process fingerprints the sources but before it acquires the file lock.
        with self.library.write_lock():
            self._ensure_steam_stopped()
            if not isinstance(plan_id, str) or plan_id not in self.plans:
                raise SteamError("分类计划已失效，请重新生成预览后再写入")
            if not isinstance(selected_ids, list) or any(
                not isinstance(value, str) for value in selected_ids
            ):
                raise SteamError("所选分类格式错误")
            stored = self.plans[plan_id]
            if time.time() - stored["created"] > PLAN_TTL_SECONDS:
                self.plans.pop(plan_id, None)
                raise SteamError("分类计划已超过 30 分钟，请重新生成预览")
            current_account = self.library.resolve_account()
            if stored["account_id"] != current_account:
                raise SteamError("Steam 账号已变化，请重新生成预览")
            if stored["source_fingerprint"] != self._source_fingerprint():
                self._clear_plans()
                raise SteamError("Steam 库数据已变化，请重新生成预览后再写入")
            valid_ids = {group["id"] for group in stored["groups"]}
            selected = set(selected_ids)
            unknown = selected - valid_ids
            if unknown:
                raise SteamError("所选分类不属于该计划，请重新生成预览")
            chosen = [group for group in stored["groups"] if group["id"] in selected]
            if not chosen:
                raise SteamError("没有选中任何分类")
            # apply_groups acquires the same lock for direct Core callers. The
            # Core lock is thread-reentrant, so this nested call cannot deadlock.
            result = self.library.apply_groups(copy.deepcopy(chosen))
            response = {**result, "plan_id": plan_id}
            self._clear_plans()
            return response

    def restore(self) -> dict[str, str | None]:
        with self.library.write_lock():
            self._ensure_steam_stopped()
            self.library.resolve_account()
            result = self.library.restore_latest()
            self._clear_plans()
            return result


def steam_running() -> bool:
    if os.name != "nt":
        return False
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq steam.exe"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        )
    except Exception as exc:
        raise SteamError(f"无法确认 Steam 是否仍在运行：{exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "tasklist 执行失败").strip()
        raise SteamError(f"无法确认 Steam 是否仍在运行：{detail}")
    return "steam.exe" in completed.stdout.lower()


ORGANIZER = Organizer()


class Handler(BaseHTTPRequestHandler):
    server_version = "SteamOrganizer/2.0"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    # ------------------------------------------------------------------ utils
    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, data) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError as exc:
            raise SteamError("请求长度格式错误") from exc
        if length < 0:
            raise SteamError("请求长度不能为负数")
        if not length:
            return {}
        if length > 1_000_000:
            raise SteamError("请求内容过大")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise SteamError("请求 JSON 格式错误") from exc
        if not isinstance(payload, dict):
            raise SteamError("请求 JSON 必须是对象")
        return payload

    def _request_security_error(self, require_token: bool = False) -> str | None:
        """Reject remote, rebinding and cross-site requests before routing."""
        try:
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                return "只允许本机访问"
        except ValueError:
            return "无法确认请求来源"

        raw_host = self.headers.get("Host") or ""
        try:
            host = urlparse("//" + raw_host)
            host_port = host.port
        except ValueError:
            return "Host 格式错误"
        expected_port = int(self.server.server_address[1])
        if (
            host.username is not None
            or host.password is not None
            or host.hostname not in {"127.0.0.1", "localhost", "::1"}
            or host_port != expected_port
        ):
            return "拒绝非本机 Host"

        origin_value = self.headers.get("Origin")
        if origin_value:
            try:
                origin = urlparse(origin_value)
                origin_port = origin.port
            except ValueError:
                return "Origin 格式错误"
            if (
                origin.scheme != "http"
                or origin.username is not None
                or origin.password is not None
                or origin.hostname not in {"127.0.0.1", "localhost", "::1"}
                or origin_port != expected_port
                or origin.path not in ("", "/")
                or origin.params
                or origin.query
                or origin.fragment
            ):
                return "拒绝跨站请求"

        if require_token:
            content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return "POST 请求必须使用 application/json"
            supplied = self.headers.get("X-Steam-Organizer-Token") or ""
            if not supplied or not secrets.compare_digest(supplied, CSRF_TOKEN):
                return "安全令牌无效，请刷新页面后重试"
        return None

    # -------------------------------------------------------------------- GET
    def do_GET(self) -> None:
        security_error = self._request_security_error()
        if security_error:
            self._json(403, {"error": security_error})
            return
        parsed_request = urlparse(self.path)
        route = parsed_request.path
        if route == "/api/state":
            with ORGANIZER.lock:
                try:
                    ORGANIZER.library.resolve_account()
                    refresh_metadata = parse_qs(parsed_request.query).get("refresh") == ["1"]
                    self._json(200, ORGANIZER.state(refresh_metadata=refresh_metadata))
                except SteamError as exc:
                    self._json(200, {"error": str(exc)})
            return
        if route in ("/", "/index.html"):
            self._serve_file("index.html")
            return
        self._serve_file(route.lstrip("/"))

    def _serve_file(self, relative: str) -> None:
        target = (UI_DIR / relative).resolve()
        try:
            target.relative_to(UI_DIR.resolve())
        except ValueError:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        if not target.is_file():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    # ------------------------------------------------------------------- POST
    def do_POST(self) -> None:
        security_error = self._request_security_error(require_token=True)
        if security_error:
            self._json(403, {"error": security_error})
            return
        route = urlparse(self.path).path
        with ORGANIZER.lock:
            try:
                payload = self._body()
                if route == "/api/plan":
                    ORGANIZER.set_language(payload.get("language") or "schinese")
                    modes = payload.get("modes") or []
                    try:
                        developer_min = int(payload.get("developer_min") or 3)
                    except (TypeError, ValueError) as exc:
                        raise SteamError("厂商最少游戏数必须是整数") from exc
                    scope = str(payload.get("scope") or "library")
                    self._json(200, ORGANIZER.make_plan(modes, developer_min, scope))
                elif route == "/api/apply":
                    result = ORGANIZER.apply(
                        payload.get("plan_id") or "",
                        payload.get("selected") or [],
                    )
                    response = dict(result)
                    try:
                        response["state"] = ORGANIZER.state()
                    except Exception as exc:  # mutation already succeeded
                        response["state_error"] = f"{type(exc).__name__}: {exc}"
                    self._json(200, response)
                elif route == "/api/restore":
                    result = ORGANIZER.restore()
                    response = dict(result)
                    try:
                        response["state"] = ORGANIZER.state()
                    except Exception as exc:  # mutation already succeeded
                        response["state_error"] = f"{type(exc).__name__}: {exc}"
                    self._json(200, response)
                elif route == "/api/owned":
                    games = ORGANIZER.library.owned_games(payload.get("api_key") or "")
                    owned = ORGANIZER.set_owned_games(games)
                    self._json(200, {"owned": owned, "state": ORGANIZER.state()})
                elif route == "/api/reveal":
                    folder = ORGANIZER.library.cloud_path().parent
                    os.startfile(str(folder))  # noqa: S606 - local convenience only
                    self._json(200, {"opened": str(folder)})
                else:
                    self._json(404, {"error": "unknown route"})
            except SteamError as exc:
                self._json(400, {"error": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_OPTIONS(self) -> None:
        # The UI is same-origin and never needs CORS. Explicitly handling
        # OPTIONS makes cross-origin preflights fail closed without a 501.
        security_error = self._request_security_error()
        if security_error or self.headers.get("Origin"):
            self._json(403, {"error": security_error or "不允许跨域请求"})
            return
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()


def serve(port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    if not UI_DIR.is_dir():
        raise SystemExit(f"UI folder missing: {UI_DIR}")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Steam Library Organizer running at {url}")
    print("Close this window to stop the server.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT)
