"""Offline franchise matching from cached metadata and explicit title aliases.

No fuzzy prefix grouping: similar titles and shared publishers alone do not
establish a series. Unknown titles remain available for manual organization.
"""
from __future__ import annotations

import re
import unicodedata


# These are aliases of a series, not a catalog of individual app IDs. Longer
# names win, so a subseries such as Red Dead Redemption stays specific.
SERIES_ALIASES = {
    "女神异闻录": ("Persona", "女神异闻录", "女神異聞錄"),
    "真·女神转生": ("Shin Megami Tensei", "真·女神转生", "真女神转生", "真女神轉生"),
    "生化危机": ("Resident Evil", "Biohazard", "生化危机", "生化危機", "惡靈古堡"),
    "最终幻想": ("Final Fantasy", "最终幻想", "最終幻想"),
    "勇者斗恶龙": ("Dragon Quest", "勇者斗恶龙", "勇者鬥惡龍"),
    "黑暗之魂": ("Dark Souls", "黑暗之魂", "黑暗靈魂"),
    "艾尔登法环": ("Elden Ring", "艾尔登法环", "艾爾登法環"),
    "装甲核心": ("Armored Core", "装甲核心", "機戰傭兵"),
    "怪物猎人": ("Monster Hunter", "怪物猎人", "魔物獵人"),
    "如龙": ("Yakuza", "Like a Dragon", "如龙", "人中之龍"),
    "审判": ("Judgment", "Lost Judgment", "审判之眼", "审判之逝", "審判之眼", "審判之逝"),
    "轨迹": ("The Legend of Heroes", "英雄传说", "英雄傳說"),
    "伊苏": ("Ys", "伊苏", "伊蘇"),
    "刺客信条": ("Assassin's Creed", "Assassins Creed", "刺客信条", "刺客教條"),
    "孤岛惊魂": ("Far Cry", "孤岛惊魂", "極地戰嚎"),
    "看门狗": ("Watch Dogs", "Watch_Dogs", "看门狗", "看門狗"),
    "使命召唤": ("Call of Duty", "使命召唤", "決勝時刻"),
    "战地": ("Battlefield", "战地", "戰地風雲"),
    "侠盗猎车手": ("Grand Theft Auto", "侠盗猎车手", "俠盜獵車手"),
    "荒野大镖客": ("Red Dead Redemption", "荒野大镖客", "碧血狂殺"),
    "巫师": ("The Witcher", "巫师", "巫師"),
    "赛博朋克 2077": ("Cyberpunk 2077", "赛博朋克2077", "電馭叛客2077"),
    "上古卷轴": ("The Elder Scrolls", "上古卷轴", "上古卷軸"),
    "辐射": ("Fallout", "辐射", "異塵餘生"),
    "毁灭战士": ("DOOM", "毁灭战士", "毀滅戰士"),
    "德军总部": ("Wolfenstein", "德军总部", "德軍總部"),
    "古墓丽影": ("Tomb Raider", "Rise of the Tomb Raider", "Shadow of the Tomb Raider", "古墓丽影", "古墓奇兵"),
    "鬼泣": ("Devil May Cry", "DmC Devil May Cry", "鬼泣", "惡魔獵人"),
    "死亡空间": ("Dead Space", "死亡空间", "絕命異次元"),
    "寂静岭": ("Silent Hill", "寂静岭", "沉默之丘"),
    "地铁": ("Metro 2033", "Metro Last Light", "Metro Exodus", "Metro Awakening", "地铁2033", "地铁最后的曙光", "地铁离去"),
    "无主之地": ("Borderlands", "无主之地", "邊緣禁地"),
    "质量效应": ("Mass Effect", "质量效应", "質量效應"),
    "龙腾世纪": ("Dragon Age", "龙腾世纪", "闇龍紀元"),
    "博德之门": ("Baldur's Gate", "博德之门", "柏德之門"),
    "神界": ("Divinity", "神界"),
    "尼尔": ("NieR", "尼尔", "尼爾"),
    "传送门": ("Portal", "传送门", "傳送門"),
    "半条命": ("Half-Life", "半条命", "戰慄時空"),
    "求生之路": ("Left 4 Dead", "求生之路", "惡靈勢力"),
    "反恐精英": ("Counter-Strike", "反恐精英", "絕對武力"),
    "文明": ("Sid Meier's Civilization", "Sid Meier’s Civilization", "文明"),
    "全面战争": ("Total War", "全面战争", "全军破敌", "全軍破敵"),
    "帝国时代": ("Age of Empires", "帝国时代", "世紀帝國"),
    "十字军之王": ("Crusader Kings", "十字军之王", "十字軍之王"),
    "钢铁雄心": ("Hearts of Iron", "钢铁雄心", "鋼鐵雄心"),
    "极限竞速": ("Forza", "极限竞速", "極限競速"),
    "极品飞车": ("Need for Speed", "极品飞车", "極速快感"),
    "街头霸王": ("Street Fighter", "街头霸王", "快打旋風"),
    "铁拳": ("TEKKEN", "铁拳", "鐵拳"),
    "拳皇": ("The King of Fighters", "拳皇"),
    "空洞骑士": ("Hollow Knight", "空洞骑士", "空洞騎士"),
    "哈迪斯": ("Hades", "哈迪斯", "黑帝斯"),
    "奥日": ("Ori and the", "奥日", "聖靈之光"),
    "杀戮尖塔": ("Slay the Spire", "杀戮尖塔", "殺戮尖塔"),
    "死亡搁浅": ("Death Stranding", "死亡搁浅", "死亡擱淺"),
    "泰坦陨落": ("Titanfall", "泰坦陨落", "神兵泰坦"),
    "杀手": ("HITMAN", "杀手", "刺客任務"),
    "消逝的光芒": ("Dying Light", "消逝的光芒", "垂死之光"),
    "战神": ("God of War", "战神", "戰神"),
    "最后生还者": ("The Last of Us", "最后生还者", "最後生還者"),
    "地平线": ("Horizon Zero Dawn", "Horizon Forbidden West", "地平线零之曙光", "地平线西之绝境"),
    "蝙蝠侠：阿卡姆": ("Batman Arkham", "蝙蝠侠阿卡姆", "蝙蝠俠阿卡漢"),
    "中土世界": ("Middle-earth", "中土世界"),
    "命令与征服": ("Command & Conquer", "命令与征服", "終極動員令"),
    "生化奇兵": ("BioShock", "生化奇兵", "生化奇兵无限"),
    "弹丸论破": ("Danganronpa", "弹丸论破", "槍彈辯駁"),
    "奇异人生": ("Life is Strange", "奇异人生", "奇異人生"),
    "小小梦魇": ("Little Nightmares", "小小梦魇", "小小夢魘"),
    "逃生": ("Outlast", "The Outlast Trials", "逃生"),
    "三位一体": ("Trine", "三位一体", "三位一體"),
    "饥荒": ("Don't Starve", "饥荒", "飢荒"),
    "正当防卫": ("Just Cause", "正当防卫", "正當防衛"),
    "家园": ("Homeworld", "家园", "萬艦齊發"),
    "光环": ("Halo", "光环", "最後一戰"),
    "潜行者": ("S.T.A.L.K.E.R.", "潜行者", "浩劫殺陣"),
    "模拟人生": ("The Sims", "模拟人生", "模擬市民"),
    "杀戮空间": ("Killing Floor", "杀戮空间", "殺戮空間"),
}


def _normal(value: str) -> str:
    value = value.replace("™", "").replace("®", "")
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("’", "'")
    return re.sub(r"[\W_]+", " ", value).strip()


def _title_match(title: str, alias: str) -> bool:
    # Only match at the beginning. English aliases need a token boundary;
    # digits and Roman sequel numbers may immediately follow a known name.
    if not title.startswith(alias):
        return False
    tail = title[len(alias):]
    if not tail:
        return True
    if alias in {"portal", "hades", "文明", "杀手", "战神", "神界", "辐射"}:
        # Portal Knights and Hades' Star are unrelated games, despite sharing
        # a first word. These short names only accept a numbered sequel or a
        # small explicit set of official edition/subtitle suffixes.
        suffix = tail.strip()
        if not re.match(r"^(?:\d+|[ivx]+)(?:\s|$)", suffix):
            return alias == "portal" and suffix == "with rtx"
    return tail[0].isspace() or tail[0].isdigit() or bool(re.match(r"^[ivx]+(?:\s|$)", tail))


_ALIASES = sorted(
    [(_normal(alias), name) for name, aliases in SERIES_ALIASES.items() for alias in aliases],
    key=lambda pair: len(pair[0]), reverse=True,
)

# Some store franchise fields name a publisher's entire catalog or a
# subscription. They are not useful game-series collections.
_UMBRELLAS = {_normal(name) for name in (
    "EA Play", "EA Originals", "Electronic Arts", "WB Games", "Warner Bros. Games",
    "PlayStation Studios", "Xbox Game Studios", "505 Games Official", "Team17 Digital",
    "FrontierDev", "THQ Nordic", "Tripwire Interactive", "SEGA", "ATLUS", "CAPCOM",
    "Square Enix", "Rockstar Games", "Ubisoft", "2K", "Focus Entertainment",
)}


def _known(names: list[str], *, exact=False) -> str | None:
    for alias, series in _ALIASES:
        if any(name == alias if exact else _title_match(name, alias) for name in names):
            return series
    return None


def series_for(item: dict) -> list[str]:
    """Return game-series labels; retain metadata evidence for unknown series."""
    if not item.get("named", bool(item.get("name"))) or not item.get("form"):
        return ["资料缺失"]
    if item["form"] != "game":
        return ["非游戏内容"]
    titles = [_normal(n) for n in (item.get("name"), item.get("name_en")) if isinstance(n, str) and n.strip()]
    known = _known(titles)
    if known:
        return [known]
    companies = {_normal(n) for n in [item.get("developer"), item.get("publisher"),
                 *(item.get("developers") or []), *(item.get("publishers") or [])] if isinstance(n, str) and n.strip()}
    series, seen = [], set()
    for name in item.get("franchises") or []:
        if not isinstance(name, str):
            continue
        name = re.sub(r"\s+", " ", name).strip()
        normalized = _normal(name)
        if not normalized or normalized in companies or normalized in _UMBRELLAS or normalized in seen:
            continue
        seen.add(normalized)
        label = _known([normalized], exact=True) or name
        if label not in series:
            series.append(label)
    return series or ["未识别系列"]
