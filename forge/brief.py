"""Free-text request -> structured Brief (Arabic + English).

The parser is deliberately rule based: it always produces a usable brief, with
or without an LLM in the loop.  When an LLM is available `forge.ai.planner`
refines this brief, it never replaces it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from .themes import STYLE_PRESETS, DEFAULT_STYLE

# ------------------------------------------------------------------ screens

SCREEN_KINDS: dict[str, dict] = {
    "shop":        {"ar": "المتجر",        "en": "Shop",        "feat": ["tabs", "grid", "currency", "search"]},
    "inventory":   {"ar": "الحقيبة",       "en": "Inventory",   "feat": ["tabs", "grid", "slot_info"]},
    "main_menu":   {"ar": "القائمة الرئيسية", "en": "Main Menu", "feat": ["buttons", "player_card", "currency"]},
    "settings":    {"ar": "الإعدادات",     "en": "Settings",    "feat": ["toggles", "sliders", "tabs"]},
    "loading":     {"ar": "شاشة التحميل",  "en": "Loading",     "feat": ["progress", "tips"]},
    "leaderboard": {"ar": "المتصدرون",     "en": "Leaderboard", "feat": ["list", "avatar", "rank"]},
    "profile":     {"ar": "الملف الشخصي",  "en": "Profile",     "feat": ["avatar", "stats", "progress"]},
    "hud":         {"ar": "واجهة اللعب",   "en": "In-game HUD", "feat": ["health", "ammo", "minimap", "hotbar"]},
    "pause":       {"ar": "قائمة الإيقاف", "en": "Pause Menu",  "feat": ["buttons"]},
    "login":       {"ar": "تسجيل الدخول",  "en": "Login",       "feat": ["inputs", "buttons"]},
    "crate":       {"ar": "فتح الصناديق",  "en": "Crate / Unbox", "feat": ["slots", "rarity", "progress"]},
    "quests":      {"ar": "المهام",        "en": "Quests",      "feat": ["list", "progress", "reward"]},
    "dialog":      {"ar": "نافذة حوار",    "en": "Dialog",      "feat": ["buttons", "text"]},
    "wheel":       {"ar": "عجلة الحظ",     "en": "Spin Wheel",  "feat": ["wheel", "rarity"]},
    "chat":        {"ar": "الدردشة",       "en": "Chat",        "feat": ["list", "input"]},
    "store":       {"ar": "متجر العملات",  "en": "Currency Store", "feat": ["cards", "currency"]},
}

DEFAULT_KIND = "main_menu"

_KIND_KEYWORDS: dict[str, list[str]] = {
    "shop": ["متجر", "المحل", "shop", "store menu", "buy", "شراء", "مبيعات"],
    "inventory": ["حقيبة", "مخزون", "inventory", "backpack", "items", "عناصر", "شنطة"],
    "main_menu": ["قائمة رئيسية", "القائمة الرئيسية", "main menu", "lobby", "لوبي", "الهوم", "home screen", "الصفحة الرئيسية"],
    "settings": ["اعدادات", "إعدادات", "setting", "options", "خيارات", "config"],
    "loading": ["تحميل", "loading", "load screen", "splash", "شاشة دخول"],
    "leaderboard": ["متصدر", "ترتيب", "leaderboard", "ranking", "rank", "top players", "لوحة الشرف"],
    "profile": ["بروفايل", "ملف شخصي", "profile", "حسابي", "account"],
    "hud": ["hud", "واجهة اللعب", "شريط صحة", "health bar", "in-game", "in game ui", "ذخيرة", "ammo"],
    "pause": ["ايقاف", "إيقاف", "pause", "استئناف", "resume menu"],
    "login": ["تسجيل دخول", "login", "sign in", "كلمة السر", "password", "username", "اسم المستخدم"],
    "crate": ["صندوق", "صناديق", "crate", "unbox", "case", "فتح صندوق"],
    "quests": ["مهام", "مهمة", "quest", "missions", "تحديات", "achievements", "انجازات", "إنجازات"],
    "dialog": ["حوار", "dialog", "popup", "نافذة منبثقة", "تأكيد", "confirm", "رسالة"],
    "wheel": ["عجلة", "wheel", "spin", "دوران", "حظ"],
    "chat": ["شات", "chat", "دردشة", "رسائل", "messages"],
    "store": ["عملات", "gems", "جواهر", "currency", "robux", "coins", "robucks"],
}

_STYLE_KEYWORDS: dict[str, list[str]] = {
    "neon": ["نيون", "neon", "مضيء", "glow", "مشع"],
    "cyber": ["سايبر", "cyber", "cyberpunk", "مستقبلي", "futuristic", "tech"],
    "royal": ["ذهبي", "gold", "ذهبيه", "فاخر", "luxury", "ملكي", "royal", "بريميوم", "premium"],
    "ocean": ["ازرق", "أزرق", "blue", "بحر", "ocean", "سماوي", "ماء"],
    "toxic": ["اخضر", "أخضر", "green", "سام", "toxic", "lime"],
    "lava": ["احمر", "أحمر", "red", "ناري", "fire", "حمم", "lava", "لهب"],
    "candy": ["كرتون", "cartoon", "اطفال", "أطفال", "مرح", "fun", "candy", "cute", "لطيف"],
    "minimal": ["بسيط", "simple", "minimal", "نظيف", "clean", "هادئ"],
    "midnight": ["غامق", "داكن", "dark", "ليل", "midnight", "اسود", "أسود", "black"],
    "military": ["عسكري", "military", "تكتيك", "tactical", "حرب", "war", "جيش"],
    "sunset": ["برتقالي", "orange", "غروب", "sunset", "دافي", "warm"],
    "forest": ["غابة", "forest", "طبيعة", "nature", "زيتي"],
    "mono": ["ابيض واسود", "أبيض وأسود", "monochrome", "mono", "رمادي", "gray", "grey"],
    "ice": ["فاتح", "light", "ابيض", "أبيض", "white", "ثلج", "snow", "ice", "جليد"],
    "grape": ["بنفسجي", "purple", "violet", "ارجواني", "أرجواني", "grape"],
    "rose": ["وردي", "pink", "زهري", "rose", "فوشيا"],
}

_LIGHT_WORDS = ["فاتح", "light", "ابيض", "أبيض", "white", "نهاري", "light mode"]
_DARK_WORDS = ["غامق", "داكن", "dark", "ليلي", "dark mode", "اسود", "أسود"]
_COMPACT_WORDS = ["مضغوط", "صغير", "compact", "small", "mini"]
_SPACIOUS_WORDS = ["واسع", "كبير", "spacious", "large", "big", "wide", "ضخم"]

_FEATURE_KEYWORDS: dict[str, list[str]] = {
    "tabs": ["تبويبات", "tabs", "اقسام", "أقسام", "categories", "فئات"],
    "grid": ["شبكة", "grid", "مربعات", "slots", "خانات"],
    "search": ["بحث", "search", "فلتر", "filter"],
    "currency": ["عملات", "جواهر", "coins", "gems", "robux", "رصيد", "balance"],
    "avatar": ["افATAR", "avatar", "صورة اللاعب", "بروفايل", "profile pic"],
    "stats": ["احصائيات", "إحصائيات", "stats", "ارقام", "أرقام"],
    "progress": ["تقدم", "progress", "bar", "شريط", "مستوى", "level", "xp"],
    "notification": ["اشعار", "إشعار", "notification", "toast", "تنبيه"],
    "sidebar": ["قائمة جانبية", "sidebar", "side menu", "جانبي"],
    "player_card": ["بطاقة اللاعب", "player card", "بطاقتي"],
    "toggles": ["مفاتيح", "toggles", "switch", "on off"],
    "sliders": ["سلايدر", "sliders", "مستوى الصوت", "volume"],
    "inputs": ["خانات ادخال", "input", "text field", "كتابة"],
    "list": ["قائمة", "list", "rows", "صفوف"],
    "hotbar": ["hotbar", "شريط سريع", "quick bar"],
}

_TITLE_RE = re.compile(
    r"(?:باسم|بعنوان|titled|named|called|title)\s*[:\-–]?\s*[\"'“”«]?\s*([^\"'”»\n،,]{2,60})",
    re.IGNORECASE,
)
_QUOTED_RE = re.compile(r"[\"“«]([^\"”»]{2,60})[\"”»]")


@dataclass
class Brief:
    raw: str = ""
    kind: str = DEFAULT_KIND
    style: str = DEFAULT_STYLE
    hue: float | None = None
    sat: float | None = None
    dark: bool | None = None
    density: str = "comfortable"          # compact | comfortable | spacious
    lang: str = "ar"                      # ar | en
    title: str = ""
    subtitle: str = ""
    features: list[str] = field(default_factory=list)
    radius: int | None = None
    polish: int = 3                       # 1..5 -> extra detail passes
    matched_keywords: list[str] = field(default_factory=list)

    # --- derived helpers -------------------------------------------------
    @property
    def screen(self) -> dict:
        return SCREEN_KINDS.get(self.kind, SCREEN_KINDS[DEFAULT_KIND])

    def has(self, *names: str) -> bool:
        return any(n in self.features for n in names)

    def label(self, ar: str, en: str) -> str:
        return ar if self.lang == "ar" else en

    def to_dict(self) -> dict:
        d = asdict(self)
        d["screen"] = self.screen
        return d


def _norm(text: str) -> str:
    t = (text or "").lower().strip()
    # unify Arabic alef/ya/ta-marbuta + strip diacritics/tatweel
    t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", t)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    return t


def detect_lang(text: str) -> str:
    return "ar" if re.search(r"[\u0600-\u06FF]", text or "") else "en"


def _match(text: str, words: list[str]) -> str | None:
    for w in words:
        if w in text:
            return w
    return None


def parse(text: str, kind: str | None = None, style: str | None = None,
          hue: float | None = None, dark: bool | None = None, lang: str | None = None) -> Brief:
    """Turn a free-text request into a :class:`Brief`."""
    raw = text or ""
    t = _norm(raw)
    matched: list[str] = []

    # --- screen kind
    chosen = kind if kind in SCREEN_KINDS else None
    if not chosen:
        best, best_len = None, 0
        for k, words in _KIND_KEYWORDS.items():
            hit = _match(t, [_norm(w) for w in words])
            if hit and len(hit) > best_len:
                best, best_len = k, len(hit)
                matched.append(hit)
        chosen = best or DEFAULT_KIND

    # --- style / colours
    chosen_style = style if style in STYLE_PRESETS else None
    if not chosen_style:
        for s, words in _STYLE_KEYWORDS.items():
            hit = _match(t, [_norm(w) for w in words])
            if hit:
                chosen_style = s
                matched.append(hit)
                break
    chosen_style = chosen_style or DEFAULT_STYLE

    if dark is None:
        if _match(t, [_norm(w) for w in _LIGHT_WORDS]):
            dark = False
        elif _match(t, [_norm(w) for w in _DARK_WORDS]):
            dark = True
    if chosen_style in ("ice", "minimal", "candy", "rose") and dark is None:
        dark = False

    # --- density
    density = "comfortable"
    if _match(t, [_norm(w) for w in _COMPACT_WORDS]):
        density = "compact"
    if _match(t, [_norm(w) for w in _SPACIOUS_WORDS]):
        density = "spacious"

    # --- features (screen defaults + explicit requests)
    feats = list(SCREEN_KINDS[chosen]["feat"])
    for f, words in _FEATURE_KEYWORDS.items():
        if _match(t, [_norm(w) for w in words]) and f not in feats:
            feats.append(f)

    # --- title
    title = ""
    m = _TITLE_RE.search(raw)
    if m:
        title = m.group(1).strip()
    else:
        q = _QUOTED_RE.search(raw)
        if q:
            title = q.group(1).strip()
    if not title:
        screen = SCREEN_KINDS[chosen]
        title = screen["ar"] if detect_lang(raw) == "ar" else screen["en"]

    polish = 3
    if _match(t, ["احترافي", "professional", "فاخر", "luxury", "premium", "مبهر", "amazing", "خرافي"]):
        polish = 5
    if _match(t, ["بسيط", "simple", "minimal", "quick", "سريع"]):
        polish = max(polish - 1, 1)

    return Brief(
        raw=raw, kind=chosen, style=chosen_style, hue=hue, dark=dark, density=density,
        lang=lang or detect_lang(raw), title=title, subtitle="", features=feats,
        polish=polish, matched_keywords=sorted(set(matched)),
    )


PRESETS: list[dict] = [
    {"id": "shop_neon", "ar": "متجر نيون احترافي", "en": "Pro neon shop",
     "text": "ابغى واجهة متجر احترافية بستايل نيون مع تبويبات وشبكة عناصر وزر شراء ورصيد جواهر"},
    {"id": "main_menu", "ar": "قائمة رئيسية فخمة", "en": "Luxury main menu",
     "text": "main menu with player card, gold luxury style, play and settings buttons, currency bar"},
    {"id": "inventory", "ar": "حقيبة عناصر", "en": "Inventory grid",
     "text": "inventory UI with tabs, item grid, rarity frames and a details panel on the side"},
    {"id": "hud", "ar": "واجهة لعب HUD", "en": "In-game HUD",
     "text": "in-game HUD with health bar, ammo counter, minimap frame and a quick hotbar"},
    {"id": "loading", "ar": "شاشة تحميل", "en": "Loading screen",
     "text": "loading screen with progress bar, tips text and animated glow background"},
    {"id": "leaderboard", "ar": "لوحة المتصدرين", "en": "Leaderboard",
     "text": "leaderboard with rank rows, avatars, medals for top 3 and my rank pinned at the bottom"},
]
