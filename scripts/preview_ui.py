"""Preview the real UI with fictional, read-only data; no Steam install needed.

Run: python scripts/preview_ui.py --port 8761
Scenarios: ready, running, empty, error, plan-error. All writes are rejected.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from steam_library_core import SteamLibrary  # noqa: E402


SAMPLE_GAMES = [
    ("Baldur's Gate 3", "3", "Larian Studios"),
    ("Celeste", "23", "Maddy Makes Games"),
    ("Cities: Skylines", "28", "Colossal Order"),
    ("Cyberpunk 2077", "3", "CD PROJEKT RED"),
    ("Death Stranding", "25", "KOJIMA PRODUCTIONS"),
    ("Disco Elysium", "3", "ZA/UM"),
    ("ELDEN RING", "3", "FromSoftware"),
    ("Firewatch", "25", "Campo Santo"),
    ("Hades", "1", "Supergiant Games"),
    ("Hollow Knight", "23", "Team Cherry"),
    ("It Takes Two", "25", "Hazelight"),
    ("Journey", "25", "thatgamecompany"),
    ("Ori and the Will of the Wisps", "23", "Moon Studios"),
    ("Outer Wilds", "25", "Mobius Digital"),
    ("Portal 2", "25", "Valve"),
    ("Red Dead Redemption 2", "1", "Rockstar Games"),
    ("SEKIRO: Shadows Die Twice", "1", "FromSoftware"),
    ("Slay the Spire", "2", "Mega Crit"),
    ("Stardew Valley", "28", "ConcernedApe"),
    ("Terraria", "23", "Re-Logic"),
    ("The Witcher 3", "3", "CD PROJEKT RED"),
    ("Titanfall 2", "1", "Respawn Entertainment"),
    ("Unpacking", "23", "Witch Beam"),
    ("Valheim", "25", "Iron Gate"),
]


def sample_catalog(scope: str = "library", empty: bool = False) -> dict:
    if empty:
        return {}
    catalog = {}
    for index, (name, genre, studio) in enumerate(SAMPLE_GAMES, 1):
        catalog[index] = {
            "appid": index, "name": name, "named": True, "form": "game",
            "genres": [genre], "developer": studio, "publisher": studio,
            "installed": index % 3 == 0, "playtime": index * 133 if index % 4 else 0,
            "last_played": int(time.time()) - index * 86400 if index % 4 else 0,
        }
    if scope == "all":
        catalog[25] = {
            "appid": 25, "name": "Sample Workshop Tool", "named": True,
            "form": "tool", "genres": [], "developer": "Sample Studio",
            "publisher": "Sample Studio", "installed": False,
            "playtime": 0, "last_played": 0,
        }
    return catalog


def preview_state(scenario: str, token: str) -> dict:
    total = 0 if scenario == "empty" else len(SAMPLE_GAMES)
    return {
        "demo": True, "steam_root": r"C:\Example\Steam",
        "steamid64": "76561198000000000", "account_id": "example",
        "steam_running": scenario == "running", "appinfo_error": None,
        "scopes": {"library": total, "games": total, "all": total + bool(total)},
        "counts": {"library": total, "games": total, "all": total + bool(total),
                   "installed": total // 3, "unresolved": 0, "auxiliary": bool(total)},
        "sources": {"cached": total, "installed": total // 3},
        "collections": [{"name": "周末想玩", "ours": False}, {"name": "已通关", "ours": False}],
        "csrf_token": token,
    }


class PreviewHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status: int, data, content_type="application/json; charset=utf-8"):
        payload = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def valid_origin(self) -> bool:
        host = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == host and self.headers.get("Origin", f"http://{host}") == f"http://{host}"

    def do_GET(self):
        if not self.valid_origin():
            self.respond(403, {"error": "仅允许本机同源预览"})
            return
        path = urlparse(self.path).path
        if path == "/api/state":
            if self.server.scenario == "error":
                self.respond(400, {"error": "示例场景：没有找到 Steam 安装目录，请选择正确的安装位置。"})
            else:
                self.respond(200, preview_state(self.server.scenario, self.server.token))
            return
        assets = {"/": ("index.html", "text/html"), "/index.html": ("index.html", "text/html"),
                  "/styles.css": ("styles.css", "text/css"), "/app.js": ("app.js", "text/javascript"),
                  "/p3r.css": ("p3r.css", "text/css"), "/appearance.js": ("appearance.js", "text/javascript"),
                  "/p5r.css": ("p5r.css", "text/css"),
                  "/vault.css": ("vault.css", "text/css"),
                  "/vault.js": ("vault.js", "text/javascript"),
                  "/persona-motion.css": ("persona-motion.css", "text/css"),
                  "/persona-motion.js": ("persona-motion.js", "text/javascript"),
                  "/calm.css": ("calm.css", "text/css"),
                  "/calm.js": ("calm.js", "text/javascript"),
                  "/art/p3r-profile.webp": ("art/p3r-profile.webp", "image/webp"),
                  "/art/p5r-profile.webp": ("art/p5r-profile.webp", "image/webp"),
                  "/fonts/Anton-Regular.ttf": ("fonts/Anton-Regular.ttf", "font/ttf"),
                  "/fonts/BarlowCondensed-BlackItalic.ttf": ("fonts/BarlowCondensed-BlackItalic.ttf", "font/ttf"),
                  "/theme-bootstrap.js": ("theme-bootstrap.js", "text/javascript")}
        if path not in assets:
            self.respond(404, {"error": "not found"})
            return
        name, content_type = assets[path]
        source = (PROJECT_ROOT / "steam_ui" / name).read_bytes()
        if name == "index.html":
            source = source.replace(b'id="demo-badge" class="demo-badge" hidden', b'id="demo-badge" class="demo-badge"')
        self.respond(200, source, content_type if content_type.startswith(("font/", "image/")) else content_type + "; charset=utf-8")

    def do_POST(self):
        if not self.valid_origin() or self.headers.get("X-Steam-Organizer-Token") != self.server.token:
            self.respond(403, {"error": "预览令牌无效"})
            return
        if urlparse(self.path).path != "/api/plan":
            self.respond(403, {"error": "这是只读示例，不会操作真实 Steam。请运行 steam_modern.py 使用桌面版。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 10000:
                raise ValueError("无效请求长度")
            config = json.loads(self.rfile.read(length))
            if not isinstance(config, dict):
                raise ValueError("请求必须是对象")
            if self.server.scenario == "plan-error":
                raise ValueError("示例场景：元数据刷新失败，请重新扫描后再试。")
            scope = config.get("scope", "library")
            catalog = sample_catalog(scope, self.server.scenario == "empty")
            groups = SteamLibrary("unused").build_groups(
                config.get("modes", ["initial", "genre"]),
                developer_min=int(config.get("developer_min", 3)), scope=scope, catalog=catalog,
            )
            for group in groups:
                group["sample"] = [catalog[appid]["name"] for appid in group["appids"][:6]]
            self.respond(200, {"plan_id": "read-only-example", "groups": groups,
                               "summary": {"existing_managed": 0, "manual_preserved": 2}})
        except (ValueError, TypeError, KeyError) as error:
            self.respond(400, {"error": str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8761)
    parser.add_argument("--scenario", choices=["ready", "running", "empty", "error", "plan-error"], default="ready")
    parser.add_argument("--export", type=Path, metavar="HTML", help="Export a standalone offline preview instead of starting a server")
    parser.add_argument("--appearance", choices=["vault", "p3r", "p5r", "calm"], default="vault", help="Default appearance of an exported preview; saved preferences still win")
    args = parser.parse_args()
    if args.export:
        export_preview(args.export, args.scenario, args.appearance)
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), PreviewHandler)
    server.scenario = args.scenario
    server.token = secrets.token_urlsafe(24)
    print(f"Read-only UI preview: http://127.0.0.1:{server.server_port}/ ({args.scenario})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def export_preview(destination: Path, scenario: str = "ready", appearance: str = "vault") -> None:
    """Inline the production UI and a read-only bridge for local visual review."""
    from steam_modern import load_ui_html

    plans = {}
    for scope in ("library", "games", "all"):
        catalog = sample_catalog(scope, scenario == "empty")
        groups = SteamLibrary("unused").build_groups(
            ["initial", "genre", "form", "developer", "publisher", "state", "recent", "playtime"],
            developer_min=1, scope=scope, catalog=catalog,
        )
        for group in groups:
            group["sample"] = [catalog[appid]["name"] for appid in group["appids"][:6]]
        plans[scope] = groups
    fixtures = json.dumps({"state": preview_state(scenario, "offline-preview"), "plans": plans,
                           "scenario": scenario}, ensure_ascii=False).replace("<", "\\u003c")
    bridge = r"""<script>
(() => {
  const fixture = FIXTURES;
  const unavailable = async () => { throw new Error('这是只读示例，不会操作真实 Steam。请运行桌面版使用此功能。'); };
  window.pywebview = { api: {
    get_state: async () => {
      if (fixture.scenario === 'error') throw new Error('示例场景：没有找到 Steam 安装目录。');
      return structuredClone(fixture.state);
    },
    make_plan: async (config) => {
      if (fixture.scenario === 'plan-error') throw new Error('示例场景：元数据刷新失败，请重新扫描后再试。');
      const groups = fixture.plans[config.scope].filter(group => config.modes.includes(group.mode));
      return { plan_id: 'read-only-example', groups: structuredClone(groups), summary: { existing_managed: 0, manual_preserved: 2 } };
    },
    apply: unavailable, restore: unavailable, choose_steam_root: unavailable,
    reveal_folder: unavailable, open_log_file: unavailable,
  }};
})();
</script>""".replace("FIXTURES", fixtures)
    html = load_ui_html().replace("</head>", bridge + "\n</head>", 1)
    if appearance not in {"vault", "p3r", "p5r", "calm"}:
        raise ValueError("Unknown preview appearance")
    html = html.replace("let appearance = 'vault';", f"let appearance = '{appearance}';", 1)
    html = html.replace('id="demo-badge" class="demo-badge" hidden', 'id="demo-badge" class="demo-badge"')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    print(f"Offline read-only preview: {destination.resolve()}")


if __name__ == "__main__":
    main()
