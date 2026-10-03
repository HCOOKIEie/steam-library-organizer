import json, os, re, threading, urllib.parse, urllib.request, urllib.error, webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    from pypinyin import lazy_pinyin
except ImportError:
    lazy_pinyin = None

STEAM_DEFAULT = r"D:\steam"

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Steam Library Organizer")
        self.root.geometry("1180x780")
        self.root.minsize(980, 650)
        self.games = []
        self.source = None
        self._build()
        self.scan_local()

    def _build(self):
        # Steam-inspired dark UI; all existing commands remain wired to the same methods.
        style = ttk.Style(self.root)
        style.theme_use("clam")
        bg, panel, text, muted, blue = "#171d25", "#202a36", "#e6edf5", "#91a0b3", "#66c0f4"
        self.root.configure(bg=bg)
        style.configure("TFrame", background=bg); style.configure("Panel.TFrame", background=panel)
        style.configure("TLabel", background=bg, foreground=text, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground="#ffffff")
        style.configure("Sub.TLabel", foreground=muted)
        style.configure("Card.TFrame", background=panel)
        style.configure("CardTitle.TLabel", background=panel, foreground=muted, font=("Segoe UI", 9))
        style.configure("CardValue.TLabel", background=panel, foreground="#ffffff", font=("Segoe UI", 18, "bold"))
        style.configure("TLabelframe", background=bg, foreground=text)
        style.configure("TLabelframe.Label", background=bg, foreground=blue, font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(12, 7), font=("Segoe UI", 9))
        style.configure("Accent.TButton", background="#1a9fff", foreground="#fff", padding=(18, 9), font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#38aaff")])
        style.configure("TEntry", fieldbackground="#111820", foreground=text, insertcolor=text)
        style.configure("TCheckbutton", background=panel, foreground=text)
        style.map("TCheckbutton", background=[("active", panel)])

        self.path = tk.StringVar(value=STEAM_DEFAULT)
        self.key = tk.StringVar(value=os.environ.get("STEAM_API_KEY", ""))
        self.status = tk.StringVar(value="尚未扫描")
        self.library_count = tk.StringVar(value="—"); self.installed_count = tk.StringVar(value="—"); self.category_count = tk.StringVar(value="—")

        header = ttk.Frame(self.root, padding=(24, 20, 24, 10)); header.pack(fill="x")
        ttk.Label(header, text="Steam Library Organizer", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="把混乱的游戏库，整理成你真正想要的收藏夹", style="Sub.TLabel").pack(anchor="w", pady=(3, 0))

        source = ttk.LabelFrame(self.root, text="1  ·  读取 Steam 游戏库", padding=14); source.pack(fill="x", padx=24, pady=(4, 8))
        row = ttk.Frame(source); row.pack(fill="x")
        ttk.Label(row, text="Steam 路径").pack(side="left")
        ttk.Entry(row, textvariable=self.path).pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(row, text="选择文件夹", command=self.choose_path).pack(side="left")
        ttk.Button(row, text="扫描本地", command=self.scan_local).pack(side="left", padx=(8, 0))
        row2 = ttk.Frame(source); row2.pack(fill="x", pady=(12, 0))
        ttk.Label(row2, text="完整库 API Key").pack(side="left")
        ttk.Entry(row2, textvariable=self.key, show="*", width=34).pack(side="left", padx=10)
        ttk.Button(row2, text="读取完整库", style="Accent.TButton", command=lambda: self.run_remote("WebApi")).pack(side="left")
        ttk.Button(row2, text="公开资料模式", command=lambda: self.run_remote("Public")).pack(side="left", padx=8)
        ttk.Button(row2, text="自动选择", command=lambda: self.run_remote("Auto")).pack(side="left")
        ttk.Button(row2, text="获取 Key 直达", command=lambda: webbrowser.open("https://steamcommunity.com/dev/apikey")).pack(side="right")
        ttk.Label(source, text="Key 仅在内存中使用，不会写入文件；中文标题将按拼音首字母分组。", style="Sub.TLabel").pack(anchor="w", pady=(10, 0))

        cards = ttk.Frame(self.root, padding=(24, 0)); cards.pack(fill="x")
        for col, title, var in ((0, "完整拥有库", self.library_count), (1, "已安装游戏", self.installed_count), (2, "可用分类", self.category_count)):
            card = ttk.Frame(cards, style="Card.TFrame", padding=(16, 10)); card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0)); cards.columnconfigure(col, weight=1)
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w"); ttk.Label(card, textvariable=var, style="CardValue.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Label(self.root, textvariable=self.status, padding=(24, 10), style="Sub.TLabel").pack(anchor="w")

        work = ttk.Frame(self.root, padding=(24, 0, 24, 10)); work.pack(fill="both", expand=True)
        left = ttk.LabelFrame(work, text="2  ·  选择分类方式", padding=12); left.pack(side="left", fill="both", expand=False, ipadx=5)
        ttk.Label(left, text="每个勾选项都会生成一个 Steam 左侧收藏夹", style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
        holder = ttk.Frame(left, style="Panel.TFrame"); holder.pack(fill="both", expand=True)
        self.cat_canvas = tk.Canvas(holder, width=330, height=330, highlightthickness=0, bg=panel)
        self.cat_canvas.pack(side="left", fill="both", expand=True)
        cat_scroll = ttk.Scrollbar(holder, orient="vertical", command=self.cat_canvas.yview); cat_scroll.pack(side="right", fill="y"); self.cat_canvas.configure(yscrollcommand=cat_scroll.set)
        self.cat_frame = ttk.Frame(self.cat_canvas, style="Panel.TFrame"); self.cat_canvas.create_window((0, 0), window=self.cat_frame, anchor="nw")
        self.cat_frame.bind("<Configure>", lambda e: self.cat_canvas.configure(scrollregion=self.cat_canvas.bbox("all"))); self.cat_vars = {}
        actions = ttk.Frame(left); actions.pack(fill="x", pady=(10, 0)); ttk.Button(actions, text="全选", command=self.select_all_categories).pack(side="left"); ttk.Button(actions, text="清空", command=self.clear_categories).pack(side="left", padx=6)

        right = ttk.LabelFrame(work, text="3  ·  日志与验证", padding=12); right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        ttk.Label(right, text="这里会显示网络请求、读取数量、备份位置和写入结果", style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
        log_frame = ttk.Frame(right); log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, wrap="word", state="disabled", font=("Consolas", 10), bg="#111820", fg="#c8d4e3", insertbackground="#fff", relief="flat", padx=12, pady=10)
        self.log.pack(side="left", fill="both", expand=True); scroll = ttk.Scrollbar(log_frame, command=self.log.yview); scroll.pack(side="right", fill="y"); self.log.configure(yscrollcommand=scroll.set)

        bottom = ttk.Frame(self.root, padding=(24, 8, 24, 18)); bottom.pack(fill="x")
        ttk.Button(bottom, text="导出报告", command=self.export_report).pack(side="left")
        ttk.Button(bottom, text="检查分类存储", command=self.inspect_collection_storage).pack(side="left", padx=8)
        ttk.Button(bottom, text="打开预览 JSON", command=self.open_preview).pack(side="left")
        self.preview_btn = ttk.Button(bottom, text="生成分类预览", command=self.make_category_preview, state="disabled"); self.preview_btn.pack(side="left", padx=8)
        self.apply_btn = ttk.Button(bottom, text="确认并写入 Steam", style="Accent.TButton", command=self.apply_selected, state="disabled"); self.apply_btn.pack(side="right")

    def write(self, text):
        self.log.configure(state="normal"); self.log.insert("end", text + "\n"); self.log.see("end"); self.log.configure(state="disabled")

    def choose_path(self):
        p = filedialog.askdirectory(initialdir=self.path.get())
        if p: self.path.set(p); self.scan_local()

    def scan_local(self):
        root = Path(self.path.get()); self.games = []
        self.write("=== 本地扫描 ===")
        if not root.exists(): self.status.set("Steam 路径不存在"); self.write(f"失败：路径不存在 {root}"); return
        login = root / "config" / "loginusers.vdf"
        if not login.exists(): self.status.set("未找到 loginusers.vdf"); self.write(f"失败：{login}"); return
        s = login.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'"(7656119\d+)"\s*\{\s*"AccountName".*?"AutoLogin"\s+"1"', s, re.S)
        if not m: self.status.set("未找到自动登录账号"); self.write("失败：无法从 loginusers.vdf 判断当前账号"); return
        self.steamid = m.group(1); self.write(f"当前 SteamID64：{self.steamid}")
        libvdf = root / "steamapps" / "libraryfolders.vdf"
        libs = [root]
        if libvdf.exists():
            for x in re.findall(r'"path"\s+"([^"]+)"', libvdf.read_text(encoding="utf-8", errors="ignore")):
                x = x.replace('\\\\','\\')
                if x not in libs: libs.append(Path(x))
        self.write("库路径：" + ", ".join(map(str, libs)))
        for lib in libs:
            for f in (lib / "steamapps").glob("appmanifest_*.acf"):
                t = f.read_text(encoding="utf-8", errors="ignore")
                a = re.search(r'"appid"\s+"(\d+)"', t); n = re.search(r'"name"\s+"([^"]*)"', t)
                if a and n: self.games.append({"appid": a.group(1), "name": n.group(1), "installed": True})
        self.installed_count.set(str(len(self.games))); self.library_count.set("—"); self.category_count.set("—")
        self.status.set(f"本地已安装：{len(self.games)}；完整库：尚未读取")
        self.write(f"已安装游戏：{len(self.games)}")
        self.write("说明：本地 manifest 不能代表完整拥有库，因此不会冒充完整结果。")

    def run_remote(self, mode):
        self.status.set(f"正在请求：{mode} …")
        threading.Thread(target=self._remote, args=(mode,), daemon=True).start()

    def _remote(self, mode):
        self.root.after(0, lambda: self.write(f"=== {mode} 请求开始 ==="))
        try:
            if mode in ("Auto", "WebApi"):
                try:
                    games = self.webapi()
                    self.root.after(0, lambda: self.finish_remote("WebApi", games))
                    return
                except Exception as e:
                    self.root.after(0, lambda: self.write(f"Web API 失败：{type(e).__name__}: {e}"))
                    if mode == "WebApi": return
            games = self.public()
            self.root.after(0, lambda: self.finish_remote("Public", games))
        except Exception as e:
            self.root.after(0, lambda: self.fail_remote(mode, e))

    def webapi(self):
        key = self.key.get().strip()
        if not key: raise RuntimeError("未填写 API Key，也未设置 STEAM_API_KEY")
        q = urllib.parse.urlencode({"key":key,"steamid":self.steamid,"format":"json","include_appinfo":1,"include_played_free_games":1})
        return self.fetch_json("https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?"+q)["response"]["games"]

    def public(self):
        url = f"https://steamcommunity.com/profiles/{self.steamid}/games/?xml=1"
        data = self.fetch_bytes(url)
        text = data.decode("utf-8", "ignore")
        items = re.findall(r'<game>.*?<appid>(\d+)</appid>.*?<name><!\[CDATA\[(.*?)\]\]></name>', text, re.S)
        if not items: raise RuntimeError("公开资料未返回游戏；可能是游戏详情未公开，或 Steam 返回了空页面")
        return [{"appid":a,"name":n} for a,n in items]

    def fetch_bytes(self, url):
        req = urllib.request.Request(url, headers={"User-Agent":"SteamLibraryOrganizer/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r: return r.read()
        except urllib.error.HTTPError as e: raise RuntimeError(f"HTTP {e.code} {e.reason}")
        except urllib.error.URLError as e: raise RuntimeError(f"无法连接远程服务器：{e.reason}")
        except TimeoutError: raise RuntimeError("请求超时（20 秒）")

    def fetch_json(self, url):
        return json.loads(self.fetch_bytes(url).decode("utf-8"))

    def finish_remote(self, source, games):
        self.source = source; installed = {g["appid"] for g in self.games}
        self.games = [{"appid":str(g["appid"]),"name":g.get("name",""),"installed":str(g["appid"]) in installed} for g in games]
        self.library_count.set(str(len(self.games))); self.installed_count.set(str(sum(x["installed"] for x in self.games)))
        self.status.set(f"完整库读取成功：{len(self.games)}；来源：{source}；已安装：{sum(x['installed'] for x in self.games)}")
        self.write(f"成功：{source} 返回 {len(self.games)} 个游戏")
        local_ids = self.local_config_appids()
        if local_ids:
            extra = local_ids - {str(g["appid"]) for g in self.games}
            self.write(f"范围说明：Steam 本地配置可见 {len(local_ids)} 个 AppID；其中 {len(extra)} 个未出现在 API 游戏列表。Steam 左侧总数还可能包含 DLC/工具/试玩等项目。")
        self.write("完整库数据已进入内存；下一步点击‘生成分类预览’查看各分类数量。")
        self.preview_btn.configure(state="normal")
        out = Path(__file__).with_name("steam_categories_preview.json")
        out.write_text(json.dumps({"source":source,"steamid64":self.steamid,"games":self.games},ensure_ascii=False,indent=2), encoding="utf-8")
        self.write(f"预览已写入：{out}")
        self.populate_categories()

    def populate_categories(self):
        for child in self.cat_frame.winfo_children(): child.destroy()
        self.cat_vars = {}
        groups = {}
        for g in self.games:
            name = (g.get("name") or "").strip()
            initial = self.initial_for_name(name)
            groups[f"拼音首字母 / {initial}"] = groups.get(f"拼音首字母 / {initial}", 0) + 1
            state = "已安装" if g.get("installed") else "未安装"
            groups[f"状态 / {state}"] = groups.get(f"状态 / {state}", 0) + 1
        local_ids = self.local_config_appids()
        missing = local_ids - {str(g["appid"]) for g in self.games}
        if missing:
            groups["其他 / API 未返回（需补充资料）"] = len(missing)
            self.write(f"提示：Steam 本地记录还有 {len(missing)} 个 AppID 不在 API 返回的 {len(self.games)} 个游戏中；它们可能是 DLC、工具、免费/未游玩项目或资料未公开。")
        ttk.Label(self.cat_frame, text="勾选后才会纳入写入计划", foreground="#555").pack(anchor="w", pady=(0,5))
        for label, count in sorted(groups.items()):
            var = tk.BooleanVar(value=True)
            self.cat_vars[label] = var
            ttk.Checkbutton(self.cat_frame, text=f"{label} ({count})", variable=var).pack(anchor="w")
        self.category_count.set(str(len(groups)))
        self.write("分类选择已生成：左侧勾选你要使用的分类。")
        if lazy_pinyin is None:
            self.write("警告：未检测到 pypinyin，中文将暂时归入‘中文’；安装依赖后可按拼音首字母分类。")
        self.apply_btn.configure(state="normal")

    def select_all_categories(self):
        for v in self.cat_vars.values(): v.set(True)

    def clear_categories(self):
        for v in self.cat_vars.values(): v.set(False)

    def make_category_preview(self):
        if not self.games:
            self.write("无法生成分类：还没有完整库数据，请先测试 Web API 或公开资料。")
            return
        groups = {"拼音首字母": {}, "入库/状态": {"已安装": 0, "未安装": 0}}
        for g in self.games:
            name = (g.get("name") or "").strip()
            initial = self.initial_for_name(name)
            groups["拼音首字母"][initial] = groups["拼音首字母"].get(initial, 0) + 1
            groups["入库/状态"]["已安装" if g.get("installed") else "未安装"] += 1
        self.write("=== 分类预览 ===")
        self.write("拼音首字母：" + ", ".join(f"{k}({v})" for k,v in sorted(groups["拼音首字母"].items())))
        self.write("状态：" + ", ".join(f"{k}({v})" for k,v in groups["入库/状态"].items()))
        self.write("类型/厂商/发行年份需要商店元数据；当前网络成功后可继续补齐。")

    def apply_selected(self):
        selected = [k for k,v in self.cat_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("未选择分类", "请至少勾选一个分类。"); return
        ok = messagebox.askyesno("确认写入 Steam", f"将写入 {len(selected)} 个分类，覆盖 {len(self.games)} 个已读取游戏。\n\n会备份 Steam 云收藏夹文件；Steam 必须完全退出。旧版自动分类记录会被清理。是否继续？")
        if not ok: return
        if os.name == "nt":
            import subprocess
            running = subprocess.run(["tasklist","/FI","IMAGENAME eq steam.exe"], capture_output=True, text=True).stdout.lower()
            if "steam.exe" in running:
                messagebox.showerror("Steam 仍在运行", "请先从 Steam 菜单选择‘退出’，确认任务管理器中没有 steam.exe 后再写入。")
                return
        try:
            backup, changed = self.write_steam_collections(selected)
            self.write(f"已写入 Steam 收藏夹数据：{changed} 个分类；覆盖完整库 {len(self.games)} 个游戏。")
            self.write(f"备份文件：{backup}")
            self.write("注意：这是文件写入成功，不等于界面已验证。请启动 Steam，打开左侧‘收藏夹’，确认分类出现后再视为完成。")
            self.status.set(f"文件已写入 {changed} 个分类；等待重启 Steam 验证")
            messagebox.showinfo("已写入，等待验证", f"已写入 {changed} 个收藏夹分类。\n\n备份：{backup}\n\n请完全退出并重新启动 Steam，然后查看左侧是否出现分类。界面出现前不要再次写入。")
        except Exception as e:
            self.write(f"写入失败：{type(e).__name__}: {e}")
            messagebox.showerror("写入失败", str(e))

    def write_steam_collections(self, selected):
        """Write the format used by current Steam Library custom collections.

        Steam stores these as JSON records in cloudstorage/cloud-storage-namespace-1.json,
        not as per-app `tags` in localconfig.vdf. Steam must be fully closed before calling.
        """
        cfgdir = Path(self.path.get()) / "userdata" / str(int(self.steamid) - 76561197960265728) / "config"
        cloud = cfgdir / "cloudstorage" / "cloud-storage-namespace-1.json"
        if not cloud.exists(): raise RuntimeError(f"找不到 Steam 云收藏夹文件：{cloud}")
        stamp = __import__("time").strftime("%Y%m%d-%H%M%S")
        backup = Path(str(cloud) + "." + stamp + ".bak")
        backup.write_bytes(cloud.read_bytes())
        try:
            records = json.loads(cloud.read_text(encoding="utf-8"))
        except Exception as e:
            raise RuntimeError(f"无法解析 Steam 云收藏夹 JSON：{e}")
        if not isinstance(records, list):
            raise RuntimeError("Steam 云收藏夹文件格式异常（预期为数组）")

        # Build selected collection -> appids from the complete owned library.
        groups = {label: [] for label in selected}
        for g in self.games:
            name = (g.get("name") or "").strip()
            initial = next((c.upper() for c in name if c.isalnum()), "#")
            state = "已安装" if g.get("installed") else "未安装"
            labels = [f"拼音首字母 / {initial}", f"状态 / {state}"]
            for label in labels:
                if label in groups: groups[label].append(int(g["appid"]))

        if "其他 / API 未返回（需补充资料）" in groups:
            local_ids = self.local_config_appids()
            known_ids = {str(g["appid"]) for g in self.games}
            groups["其他 / API 未返回（需补充资料）"] = [int(x) for x in sorted(local_ids - known_ids) if x.isdigit()]

        import hashlib, time
        # Remove collections produced by previous runs. Otherwise old rules remain
        # visible beside the corrected ones and make Steam appear to have duplicates.
        records = [r for r in records if not (isinstance(r, list) and len(r) == 2 and isinstance(r[0], str) and r[0].startswith("user-collections.auto-"))]
        index = {r[0]: r for r in records if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str)}
        now = int(time.time())
        for label, appids in groups.items():
            cid = "auto-" + hashlib.sha1(label.encode("utf-8")).hexdigest()[:12]
            key = "user-collections." + cid
            value = json.dumps({"id": cid, "name": label, "added": sorted(set(appids)), "removed": []}, ensure_ascii=False, separators=(",", ":"))
            old = index.get(key)
            meta = dict(old[1]) if old and isinstance(old[1], dict) else {"key": key}
            meta.update({"key": key, "value": value, "timestamp": now, "version": str(meta.get("version", "366"))})
            rec = [key, meta]
            if old:
                records[records.index(old)] = rec
            else:
                records.append(rec)
        cloud.write_text(json.dumps(records, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="")
        return str(backup), len(groups)

    @staticmethod
    def initial_for_name(name):
        """Return an A-Z/digit bucket using pinyin for Chinese titles."""
        for c in (name or "").strip():
            if c.isascii() and c.isalpha(): return c.upper()
            if c.isascii() and c.isdigit(): return "数字"
            if "\u4e00" <= c <= "\u9fff":
                if lazy_pinyin:
                    for syllable in lazy_pinyin((name or "").strip(), errors="ignore"):
                        if syllable and syllable[0].isalpha(): return syllable[0].upper()
                return "中文"
        return "其他"

    def local_config_appids(self):
        """App IDs currently known by Steam's local library config."""
        if not hasattr(self, "steamid"): return set()
        p = Path(self.path.get()) / "userdata" / str(int(self.steamid) - 76561197960265728) / "config" / "localconfig.vdf"
        if not p.exists(): return set()
        text = p.read_text(encoding="utf-8", errors="ignore")
        pos = text.find('"apps"')
        if pos < 0: return set()
        return set(re.findall(r'(?m)^\s*"(\d+)"\s*\{', text[pos:]))

    def fail_remote(self, mode, e):
        self.status.set(f"{mode} 失败：{e}"); self.write(f"最终失败：{type(e).__name__}: {e}")
        self.write("这表示请求没有拿到完整列表，不会生成假数据，也不会修改 Steam。")

    def export_report(self):
        p = Path(__file__).with_name("steam_diagnostic_report.txt")
        text = self.log.get("1.0", "end")
        p.write_text(text, encoding="utf-8"); self.write(f"诊断报告已导出：{p}")

    def open_preview(self):
        p = Path(__file__).with_name("steam_categories_preview.json")
        if not p.exists(): messagebox.showinfo("提示", "还没有预览，请先测试 Web API 或公开资料"); return
        os.startfile(str(p))

    def inspect_collection_storage(self):
        """Report the files/records Steam currently exposes for Library collections."""
        cfgdir = Path(self.path.get()) / "userdata" / str(int(getattr(self, "steamid", "0")) - 76561197960265728) / "config"
        cloud = cfgdir / "cloudstorage" / "cloud-storage-namespace-1.json"
        local = cfgdir / "localconfig.vdf"
        self.write("=== Steam 分类存储检查 ===")
        self.write(f"云存储文件：{cloud}（存在={cloud.exists()}）")
        if cloud.exists():
            try:
                records = json.loads(cloud.read_text(encoding="utf-8"))
                keys = [r[0] for r in records if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str) and r[0].startswith("user-collections.")]
                self.write(f"发现 user-collections 记录：{len(keys)}")
                self.write("记录名：" + (", ".join(keys) if keys else "（无自定义分类记录）"))
            except Exception as e:
                self.write(f"云存储解析失败：{type(e).__name__}: {e}")
        self.write(f"localconfig.vdf：{local}（存在={local.exists()}）")
        if local.exists():
            text = local.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'(?m)^\s*"user-collections"\s+"([^\"]*)"', text)
            self.write(f"localconfig 的 user-collections 值：{m.group(1) if m else '未找到'}")
        self.write("验收标准：重启 Steam 后左侧出现新分类；仅看到‘写入完成’或文件记录不算成功。")

if __name__ == "__main__":
    root = tk.Tk(); App(root); root.mainloop()
