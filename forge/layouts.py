"""Layout engine: free-text brief -> full component tree.

Layouts are built left-to-right on a 1920x1080 virtual canvas and then mirrored
when the brief language is Arabic, so RTL support is structural rather than an
afterthought.
"""
from __future__ import annotations

from dataclasses import dataclass

from .brief import Brief, SCREEN_KINDS
from .spec import Asset, DesignSpec, Node, Rect, center_in, grid, slugify, split_h, split_v
from .themes import Palette, mix, shade

# ------------------------------------------------------------------ helpers


@dataclass
class M:
    """Metrics derived from the density keyword."""
    pad: float
    gap: float
    header: float
    footer: float
    sidebar: float
    radius: int
    fs_title: int
    fs_head: int
    fs_body: int
    fs_small: int
    btn_h: float


def metrics(brief: Brief, pal: Palette) -> M:
    d = brief.density
    base = {
        "compact":     dict(pad=48, gap=12, header=84, footer=76, sidebar=230, fs=(46, 34, 24, 19), btn=68),
        "comfortable": dict(pad=72, gap=18, header=100, footer=92, sidebar=270, fs=(58, 40, 29, 23), btn=84),
        "spacious":    dict(pad=100, gap=26, header=118, footer=108, sidebar=320, fs=(70, 48, 34, 26), btn=98),
    }[d]
    r = pal.radius if brief.radius is None else brief.radius
    return M(base["pad"], base["gap"], base["header"], base["footer"], base["sidebar"],
             r, base["fs"][0], base["fs"][1], base["fs"][2], base["fs"][3], base["btn"])


def N(kind: str, name: str, rect: Rect, children: list[Node] | None = None, **props) -> Node:
    return Node(kind=kind, name=name, rect=rect, props=props, children=children or [])


def T(name: str, rect: Rect, label: str, label_en: str = "", size: int = 28,
      align: str = "left", color=None, **props) -> Node:
    props.setdefault("font_size", size)
    props.setdefault("align", align)
    if color is not None:
        props["color"] = color
    return Node(kind="text", name=name, rect=rect, props={"label": label, "label_en": label_en or label, **props})


def _polish(brief: Brief) -> int:
    return max(1, min(5, brief.polish))


# ------------------------------------------------------------------ mirroring


def mirror(node: Node, canvas_w: float) -> None:
    r = node.rect
    node.rect = Rect(canvas_w - r.x - r.w, r.y, r.w, r.h)
    p = node.props
    if p.get("align") in ("left", "right"):
        p["align"] = "right" if p["align"] == "left" else "left"
    if p.get("side") in ("left", "right"):
        p["side"] = "right" if p["side"] == "left" else "right"
    ic = p.get("icon")
    if ic in ("arrow_right", "arrow_left"):
        p["icon"] = "arrow_left" if ic == "arrow_right" else "arrow_right"
    for c in node.children:
        mirror(c, canvas_w)


# ------------------------------------------------------------------ shared parts


def window(title: str, title_en: str, brief: Brief, pal: Palette, m: M,
           rect: Rect, subtitle: str = "", subtitle_en: str = "",
           closable: bool = True, header_icon: str = "star") -> list[Node]:
    """Panel + header strip + title + close button.  Returns top level nodes."""
    nodes = [N("panel", "Window", rect, radius=m.radius, top=pal.panel_hi, bottom=pal.panel_lo,
               stroke=mix(pal.stroke, pal.accent, 0.3), stroke_w=pal.stroke_w + 1, shadow=True)]
    hdr = Rect(rect.x, rect.y, rect.w, m.header)
    nodes.append(N("panel", "Header", hdr, radius=m.radius, top=mix(pal.panel_hi, pal.accent, 0.22),
                   bottom=mix(pal.panel_hi, pal.accent, 0.05), stroke=None, header_h=0))
    nodes.append(N("icon", "HeaderIcon", Rect(rect.x + 30, hdr.cy - 26, 52, 52),
                   icon=header_icon, color=pal.accent_hi, secondary=mix(pal.accent, (255, 255, 255), 0.4)))
    nodes.append(T("Title", Rect(rect.x + 96, rect.y, rect.w * 0.5, m.header), title, title_en,
                   size=m.fs_head, align="left", color=pal.text))
    if subtitle:
        nodes.append(T("Subtitle", Rect(rect.x + 96, rect.y + m.header - 34, rect.w * 0.5, 30),
                       subtitle, subtitle_en, size=m.fs_small, align="left", color=pal.text_dim))
    nodes.append(N("divider", "HeaderLine", Rect(rect.x + 20, rect.y + m.header - 2, rect.w - 40, 2),
                   color=mix(pal.stroke, pal.accent, 0.5)))
    if closable:
        b = 52
        nodes.append(N("button", "CloseButton", Rect(rect.right - b - 26, hdr.cy - b / 2, b, b),
                       variant="ghost", radius=b / 2, label="×", font_size=34, align="center", color=pal.text))
    return nodes


def currency_pill(rect: Rect, amount: str, icon: str, pal: Palette, m: M, name: str = "Currency") -> list[Node]:
    return [
        N("badge", name, rect, color=mix(pal.panel_lo, (0, 0, 0), 0.25), radius=rect.h / 2,
          stroke=mix(pal.stroke, pal.accent, 0.35), stroke_w=pal.stroke_w),
        N("icon", f"{name}Icon", Rect(rect.x + 12, rect.cy - rect.h * 0.3, rect.h * 0.6, rect.h * 0.6),
          icon=icon, color=pal.accent_hi, secondary=mix(pal.accent, (0, 0, 0), 0.3)),
        T(f"{name}Label", Rect(rect.x + rect.h * 0.8, rect.y, rect.w - rect.h * 0.9 - 16, rect.h),
          amount, amount, size=m.fs_body, align="left", color=pal.text),
    ]


def button(rect: Rect, name: str, label: str, label_en: str, pal: Palette, m: M,
           variant: str = "primary", icon: str | None = None, size: int | None = None) -> Node:
    props = dict(variant=variant, radius=m.radius, label=label, label_en=label_en,
                 font_size=size or m.fs_body, align="center",
                 color=pal.text if variant in ("secondary", "ghost") else (255, 255, 255),
                 shadow=variant in ("primary", "danger", "success"))
    if icon:
        props["icon"] = icon
        props["icon_color"] = props["color"]
    return N("button", name, rect, **props)


def stat_card(rect: Rect, name: str, value: str, label: str, label_en: str, icon: str,
              pal: Palette, m: M, color=None) -> list[Node]:
    c = color or pal.accent
    return [
        N("panel", name, rect, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.05),
          bottom=mix(pal.panel_lo, (0, 0, 0), 0.1), stroke=mix(pal.stroke, c, 0.35), stroke_w=pal.stroke_w),
        N("icon", f"{name}Icon", Rect(rect.x + 18, rect.cy - 22, 44, 44), icon=icon, color=c,
          secondary=mix(c, (0, 0, 0), 0.3)),
        T(f"{name}Value", Rect(rect.x + 72, rect.y + rect.h * 0.12, rect.w - 88, rect.h * 0.46),
          value, value, size=m.fs_head - 6, align="left", color=pal.text),
        T(f"{name}Label", Rect(rect.x + 72, rect.y + rect.h * 0.55, rect.w - 88, rect.h * 0.34),
          label, label_en, size=m.fs_small, align="left", color=pal.text_dim),
    ]


def slot(rect: Rect, name: str, pal: Palette, m: M, rarity: int = 0, icon: str = "sword",
         label: str = "", selected: bool = False, price: str = "") -> list[Node]:
    nodes = [N("slot", name, rect, rarity=rarity, rarity_color=pal.rarity(rarity), radius=m.radius * 0.8,
               selected=selected)]
    isize = min(rect.w, rect.h) * 0.56
    nodes.append(N("icon", f"{name}Icon", Rect(rect.cx - isize / 2, rect.cy - isize / 2 - (10 if label else 0),
                                               isize, isize), icon=icon,
                   color=mix(pal.text, pal.rarity(rarity), 0.35), secondary=mix(pal.rarity(rarity), (0, 0, 0), 0.4)))
    if label:
        nodes.append(T(f"{name}Label", Rect(rect.x + 6, rect.bottom - 34, rect.w - 12, 28), label, label,
                       size=m.fs_small - 2, align="center", color=pal.text_dim))
    if price:
        pw, ph = max(78, rect.w * 0.5), 30
        nodes.append(N("badge", f"{name}PriceBg", Rect(rect.cx - pw / 2, rect.bottom - ph / 2, pw, ph),
                       color=mix(pal.bg_deep, (0, 0, 0), 0.35), radius=ph / 2,
                       stroke=mix(pal.stroke, pal.accent, 0.4), stroke_w=1))
        nodes.append(T(f"{name}Price", Rect(rect.cx - pw / 2, rect.bottom - ph / 2, pw, ph), price, price,
                       size=m.fs_small - 3, align="center", color=pal.accent_hi, icon="coin"))
    return nodes


def progress(rect: Rect, name: str, pal: Palette, m: M, value: float = 0.6,
             color=None, label: str = "", label_en: str = "", height: float | None = None,
             stripes: bool = False) -> list[Node]:
    h = height or rect.h
    r = Rect(rect.x, rect.cy - h / 2, rect.w, h)
    c = color or pal.accent
    nodes = [N("track", f"{name}Track", r, radius=h / 2)]
    fw = max(h, r.w * max(0.02, min(1.0, value)))
    nodes.append(N("fill", f"{name}Fill", Rect(r.x, r.y, fw, h), radius=h / 2, color=c, stripes=stripes))
    if label:
        nodes.append(T(f"{name}Label", Rect(r.x, r.y, r.w, h), label, label_en, size=m.fs_small,
                       align="center", color=(255, 255, 255) if value > 0.12 else pal.text))
    return nodes


def row(rect: Rect, name: str, idx: int, title: str, title_en: str, meta: str, meta_en: str,
        pal: Palette, m: M, icon: str = "user", highlight: bool = False,
        right: str = "", medal: int | None = None) -> list[Node]:
    nodes = [N("row", name, rect, index=idx, highlight=highlight, radius=m.radius * 0.7)]
    bh = min(56, rect.h - 18)
    nodes.append(N("avatar", f"{name}Avatar", Rect(rect.x + 16, rect.cy - bh / 2, bh, bh),
                   ring=pal.warn if medal == 0 else (pal.text_dim if medal == 1 else (mix(pal.warn, (120, 60, 20), 0.4) if medal == 2 else mix(pal.stroke, pal.accent, 0.5))),
                   crown=medal == 0))
    nodes.append(T(f"{name}Title", Rect(rect.x + bh + 34, rect.y + rect.h * 0.14, rect.w * 0.5, rect.h * 0.44),
                   title, title_en, size=m.fs_body, align="left", color=pal.text))
    nodes.append(T(f"{name}Meta", Rect(rect.x + bh + 34, rect.y + rect.h * 0.52, rect.w * 0.5, rect.h * 0.38),
                   meta, meta_en, size=m.fs_small, align="left", color=pal.text_dim))
    if right:
        nodes.append(T(f"{name}Right", Rect(rect.right - rect.w * 0.28, rect.y, rect.w * 0.26, rect.h),
                       right, right, size=m.fs_body, align="right", color=pal.accent_hi))
    if medal is not None:
        nodes.append(T(f"{name}Rank", Rect(rect.x - 2, rect.y, 18, rect.h), str(idx + 1), str(idx + 1),
                       size=m.fs_small, align="center", color=pal.text_dim))
    return nodes


def tab_bar(rect: Rect, names: list[str], names_en: list[str], pal: Palette, m: M,
            active: int = 0, name: str = "Tabs") -> list[Node]:
    cells = split_h(rect, [1] * len(names), gap=m.gap * 0.6)
    nodes = []
    for i, (c, ar, en) in enumerate(zip(cells, names, names_en)):
        act = i == active
        nodes.append(N("tab", f"{name}{i}", c, active=act, radius=m.radius * 0.8))
        nodes.append(T(f"{name}{i}Label", c, ar, en, size=m.fs_body - 2, align="center",
                       color=pal.text if act else pal.text_dim))
    return nodes


# ------------------------------------------------------------------ builders


def _topbar(brief: Brief, pal: Palette, m: M, canvas: tuple[int, int]) -> list[Node]:
    w, _ = canvas
    nodes: list[Node] = []
    ph = 60
    top = 28
    if brief.has("currency"):
        nodes += currency_pill(Rect(w - m.pad - 300, top, 180, ph), "12,450", "coin", pal, m, "CoinsPill")
        nodes += currency_pill(Rect(w - m.pad - 110, top, 110, ph), "320", "gem", pal, m, "GemsPill")
    if brief.has("player_card", "avatar"):
        nodes.append(N("avatar", "TopAvatar", Rect(m.pad, top, ph, ph), ring=pal.accent, crown=True))
        nodes.append(T("TopName", Rect(m.pad + ph + 14, top, 240, ph), "Player_01", "Player_01",
                       size=m.fs_body, align="left", color=pal.text))
    return nodes


def build_main_menu(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="nebula", seed=5)]
    nodes.append(N("scrim", "LeftScrim", Rect(0, 0, w * 0.52, h), alpha=0.42))
    nodes += _topbar(brief, pal, m, canvas)

    # logo / title block
    logo_h = m.fs_title * 1.9
    nodes.append(T("LogoTitle", Rect(m.pad, h * 0.24, w * 0.46, logo_h), brief.title, brief.title,
                   size=m.fs_title, align="left", color=pal.text, stroke=mix(pal.bg_deep, (0, 0, 0), 0.6)))
    nodes.append(T("LogoSubtitle", Rect(m.pad, h * 0.24 + logo_h, w * 0.44, 44),
                   brief.subtitle or "Roblox UI Forge — تصميم كامل بضغطة",
                   brief.subtitle or "Roblox UI Forge - a full UI in one click",
                   size=m.fs_head - 8, align="left", color=pal.text_dim))
    nodes.append(N("divider", "LogoDivider", Rect(m.pad, h * 0.24 + logo_h + 58, 320, 3), color=pal.accent))

    # main button column
    labels = [("العب", "Play", "play", "primary"), ("المتجر", "Shop", "cart", "secondary"),
              ("الحقيبة", "Inventory", "bag", "secondary"), ("المتصدرون", "Leaderboard", "trophy", "secondary"),
              ("الإعدادات", "Settings", "settings", "ghost")]
    bw = 380
    by = h * 0.24 + logo_h + 100
    cells = split_v(Rect(m.pad, by, bw, h - by - m.pad - 70), [1] * len(labels), gap=m.gap)
    for i, (c, (ar, en, ic, var)) in enumerate(zip(cells, labels)):
        nodes.append(button(c, f"MenuButton{i}", ar, en, pal, m, variant=var, icon=ic))

    # player card
    cw, chh = 470, 520
    card = Rect(w - m.pad - cw, h * 0.2, cw, chh)
    nodes.append(N("panel", "PlayerCard", card, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.06),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.4), stroke_w=pal.stroke_w + 1,
                   shadow=True))
    av = 150
    nodes.append(N("avatar", "CardAvatar", Rect(card.cx - av / 2, card.y + 30, av, av), ring=pal.accent, crown=True))
    nodes.append(T("CardName", Rect(card.x, card.y + 30 + av + 6, card.w, 40), "Player_01", "Player_01",
                   size=m.fs_head - 4, align="center", color=pal.text))
    nodes.append(N("badge", "CardLevel", Rect(card.cx - 60, card.y + 30 + av + 52, 120, 36),
                   color=pal.accent, radius=18))
    nodes.append(T("CardLevelLabel", Rect(card.cx - 60, card.y + 30 + av + 52, 120, 36), "المستوى 42",
                   "Level 42", size=m.fs_small, align="center", color=(255, 255, 255)))
    nodes += progress(Rect(card.x + 36, card.y + 30 + av + 104, card.w - 72, 22), "CardXP", pal, m,
                      value=0.68, label="6,800 / 10,000 XP", label_en="6,800 / 10,000 XP", stripes=True)
    srects = grid(Rect(card.x + 28, card.y + 30 + av + 150, card.w - 56, card.h - (30 + av + 190)),
                  2, 2, gap=m.gap)
    for i, (rc, val, lab, lab_en, ic, col) in enumerate(zip(
            srects, ["1,284", "327", "58", "12"],
            ["الفوز", "الجواهر", "الإنجازات", "الأيام"], ["Wins", "Gems", "Badges", "Streak"],
            ["trophy", "gem", "medal", "fire"], [pal.success, pal.accent, pal.warn, pal.danger])):
        nodes += stat_card(rc, f"CardStat{i}", val, lab, lab_en, ic, pal, m, color=col)

    # bottom social row
    srow = split_h(Rect(m.pad, h - m.pad - 62, 460, 62), [1, 1, 1], gap=m.gap)
    for i, (c, (ar, en, ic)) in enumerate(zip(srow, [("الديسكورد", "Discord", "discord"),
                                                    ("الدردشة", "Chat", "chat"),
                                                    ("الإشعارات", "Alerts", "bell")])):
        nodes.append(button(c, f"SocialButton{i}", ar, en, pal, m, variant="ghost", icon=ic, size=m.fs_small + 2))
    nodes.append(T("Version", Rect(w - m.pad - 300, h - m.pad - 40, 300, 30), "v1.0.0 — Roblox UI Forge",
                   "v1.0.0 - Roblox UI Forge", size=m.fs_small - 4, align="right", color=pal.text_dim))

    # toast sample
    if brief.has("notification") or _polish(brief) >= 4:
        t = Rect(w - m.pad - 400, h * 0.2 + chh + 30, 400, 104)
        nodes.append(N("toast", "Toast", t, color=pal.success, radius=m.radius, side="left", shadow=True))
        nodes.append(N("icon", "ToastIcon", Rect(t.x + 20, t.cy - 22, 44, 44), icon="check", color=pal.success))
        nodes.append(T("ToastTitle", Rect(t.x + 78, t.y + 14, t.w - 96, 36), "تم الحفظ!", "Saved!",
                       size=m.fs_body - 2, align="left", color=pal.text))
        nodes.append(T("ToastBody", Rect(t.x + 78, t.y + 52, t.w - 96, 34), "تم تحديث ملفك الشخصي",
                       "Your profile was updated", size=m.fs_small, align="left", color=pal.text_dim))
    return nodes


def build_shop(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="glow", seed=9)]
    win = Rect(m.pad * 0.75, m.pad * 0.7, w - m.pad * 1.5, h - m.pad * 1.4)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="cart")

    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    cols = split_h(body, [m.sidebar, 1, 380], gap=m.gap)
    side, content, detail = cols

    # sidebar categories
    nodes.append(N("panel", "SidePanel", side, radius=m.radius, top=pal.panel, bottom=mix(pal.panel_lo, (0, 0, 0), 0.15),
                   stroke=pal.stroke, stroke_w=pal.stroke_w - 1))
    cats = [("الأسلحة", "Weapons", "sword"), ("الدروع", "Armor", "shield"), ("المركبات", "Vehicles", "bolt"),
            ("الحيوانات", "Pets", "heart"), ("الباقات", "Bundles", "gift"), ("العروض", "Deals", "fire")]
    ch = split_v(Rect(side.x + 14, side.y + 18, side.w - 28, side.h - 36), [1] * len(cats), gap=m.gap * 0.7)
    for i, (c, (ar, en, ic)) in enumerate(zip(ch, cats)):
        act = i == 0
        nodes.append(N("tab", f"Cat{i}", c, active=act, radius=m.radius * 0.7))
        nodes.append(N("icon", f"Cat{i}Icon", Rect(c.x + 14, c.cy - 18, 36, 36), icon=ic,
                       color=pal.accent_hi if act else pal.text_dim, secondary=mix(pal.accent, (0, 0, 0), 0.4)))
        nodes.append(T(f"Cat{i}Label", Rect(c.x + 58, c.y, c.w - 68, c.h), ar, en, size=m.fs_body - 3,
                       align="left", color=pal.text if act else pal.text_dim))

    # top: tabs + search + currency
    top = split_h(Rect(content.x, content.y, content.w, 64), [0.9, 1.1], gap=m.gap)
    nodes += tab_bar(top[0], ["الأكثر مبيعاً", "جديد", "خصومات"], ["Top", "New", "Sale"], pal, m, name="ShopTab")
    nodes.append(N("field", "SearchField", top[1], radius=top[1].h / 2))
    nodes.append(N("icon", "SearchIcon", Rect(top[1].x + 18, top[1].cy - 17, 34, 34), icon="search",
                   color=pal.text_dim))
    nodes.append(T("SearchPlaceholder", Rect(top[1].x + 60, top[1].y, top[1].w - 80, top[1].h),
                   "ابحث عن عنصر…", "Search items...", size=m.fs_body - 4, align="left", color=pal.text_dim))

    # item grid
    grect = Rect(content.x, content.y + 64 + m.gap, content.w, content.h - 64 - m.gap - 64)
    items = [("سيف اللهب", "Flame Sword", "sword", 3, "2,400"), ("درع التنين", "Dragon Armor", "shield", 4, "5,100"),
             ("جوهرة القوة", "Power Gem", "gem", 2, "900"), ("قوس الصقر", "Falcon Bow", "bolt", 1, "640"),
             ("خوذة الفولاذ", "Steel Helm", "shield", 0, "310"), ("تعويذة الحظ", "Luck Charm", "star", 3, "1,750"),
             ("قلب التنين", "Dragon Heart", "heart", 4, "9,900"), ("مفتاح ذهبي", "Gold Key", "key", 2, "1,200"),
             ("درع الظل", "Shadow Guard", "shield", 1, "780"), ("نجمة الليل", "Night Star", "star", 0, "260")]
    cells = grid(grect, 5, 2, gap=m.gap, cell_ratio=0.82, align="center")
    for i, (c, (ar, en, ic, rar, price)) in enumerate(zip(cells, items)):
        nodes += slot(c, f"Item{i}", pal, m, rarity=rar, icon=ic, label=ar, selected=(i == 2), price=price)

    # pager
    pager = Rect(content.x, grect.bottom + m.gap, content.w, 48)
    nodes.append(N("badge", "PagePill", center_in(pager, 200, 44), color=mix(pal.panel_lo, (0, 0, 0), 0.3),
                   radius=22, stroke=pal.stroke, stroke_w=1))
    nodes.append(T("PageLabel", center_in(pager, 200, 44), "الصفحة 1 من 4", "Page 1 of 4",
                   size=m.fs_small, align="center", color=pal.text_dim))
    nodes.append(button(Rect(pager.x, pager.y, 150, 48), "PrevPage", "السابق", "Prev", pal, m,
                        variant="ghost", icon="arrow_left", size=m.fs_small + 2))
    nodes.append(button(Rect(pager.right - 150, pager.y, 150, 48), "NextPage", "التالي", "Next", pal, m,
                        variant="ghost", icon="arrow_right", size=m.fs_small + 2))

    # details panel
    nodes.append(N("panel", "DetailPanel", detail, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.06),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.45), stroke_w=pal.stroke_w + 1,
                   shadow=True))
    big = min(detail.w - 60, 260)
    nodes += slot(Rect(detail.cx - big / 2, detail.y + 30, big, big), "DetailSlot", pal, m,
                  rarity=2, icon="gem", label="")
    nodes.append(N("badge", "RarityBadge", Rect(detail.cx - 70, detail.y + 30 + big - 14, 140, 34),
                   color=pal.rarity(2), radius=17))
    nodes.append(T("RarityLabel", Rect(detail.cx - 70, detail.y + 30 + big - 14, 140, 34), "نادر جداً",
                   "Epic", size=m.fs_small - 2, align="center", color=(255, 255, 255)))
    nodes.append(T("DetailName", Rect(detail.x + 20, detail.y + 30 + big + 28, detail.w - 40, 40),
                   "جوهرة القوة", "Power Gem", size=m.fs_head - 6, align="center", color=pal.text))
    nodes.append(T("DetailDesc", Rect(detail.x + 28, detail.y + 30 + big + 74, detail.w - 56, 96),
                   "ترفع القوة الهجومية بنسبة 25% لمدة 5 دقائق. لا تُستخدم إلا مرة واحدة لكل معركة.",
                   "Boosts attack power by 25% for 5 minutes. One use per battle.",
                   size=m.fs_small, align="center", color=pal.text_dim))
    stats_y = detail.y + 30 + big + 180
    for i, (k, v, ic) in enumerate([("القوة", "+25%", "bolt"), ("الندرة", "نادر جداً", "star"), ("الوزن", "1.2", "bag")]):
        yy = stats_y + i * 44
        nodes.append(N("icon", f"DetailStat{i}Icon", Rect(detail.x + 30, yy + 4, 28, 28), icon=ic,
                       color=pal.accent_hi, secondary=mix(pal.accent, (0, 0, 0), 0.4)))
        nodes.append(T(f"DetailStat{i}Key", Rect(detail.x + 68, yy, detail.w * 0.4, 36), k, k,
                       size=m.fs_small, align="left", color=pal.text_dim))
        nodes.append(T(f"DetailStat{i}Val", Rect(detail.right - detail.w * 0.45, yy, detail.w * 0.4 - 24, 36),
                       v, v, size=m.fs_small, align="right", color=pal.text))
    nodes.append(button(Rect(detail.x + 28, detail.bottom - 130, detail.w - 56, 62), "BuyButton",
                        "شراء الآن", "Buy Now", pal, m, variant="primary", icon="cart"))
    nodes.append(button(Rect(detail.x + 28, detail.bottom - 60, detail.w - 56, 46), "WishButton",
                         "أضف للمفضلة", "Add to wishlist", pal, m, variant="ghost", icon="heart", size=m.fs_small + 1))

    # footer currency
    nodes += currency_pill(Rect(win.right - 340, win.bottom - m.footer + 16, 160, 56), "12,450", "coin", pal, m,
                           "FooterCoins")
    nodes += currency_pill(Rect(win.right - 168, win.bottom - m.footer + 16, 120, 56), "320", "gem", pal, m,
                           "FooterGems")
    nodes.append(T("FooterHint", Rect(win.x + 24, win.bottom - m.footer + 16, 600, 56),
                   "اضغط على أي عنصر لعرض التفاصيل", "Click any item to view details",
                   size=m.fs_small, align="left", color=pal.text_dim))
    return nodes


def build_inventory(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="grid", seed=3)]
    win = Rect(m.pad * 0.75, m.pad * 0.7, w - m.pad * 1.5, h - m.pad * 1.4)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="bag")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    nodes += tab_bar(Rect(body.x, body.y, body.w, 60), ["الكل", "الأسلحة", "الدروع", "المواد"],
                     ["All", "Weapons", "Armor", "Materials"], pal, m, name="InvTab")
    grid_rect = Rect(body.x, body.y + 60 + m.gap, body.w - 400 - m.gap, body.h - 60 - m.gap - 80)
    items = [("سيف", "sword", 3), ("درع", "shield", 1), ("جوهرة", "gem", 4), ("مفتاح", "key", 2),
             ("قلب", "heart", 0), ("نجمة", "star", 2), ("قوس", "bolt", 1), ("تاج", "crown", 4),
             ("هدية", "gift", 0), ("خوذة", "shield", 3), ("نار", "fire", 2), ("هدف", "target", 1),
             ("علم", "flag", 0), ("درع", "shield", 2), ("سيف", "sword", 1), ("جوهرة", "gem", 3),
             ("مفتاح", "key", 0), ("قلب", "heart", 1), ("نجمة", "star", 4), ("قوس", "bolt", 2),
             ("تاج", "crown", 3), ("هدية", "gift", 1), ("خوذة", "shield", 0), ("نار", "fire", 4)]
    cells = grid(grid_rect, 6, 4, gap=m.gap, cell_ratio=0.95, align="top")
    for i, (c, (ar, ic, rar)) in enumerate(zip(cells, items)):
        nodes += slot(c, f"InvSlot{i}", pal, m, rarity=rar, icon=ic, selected=(i == 2))
    # sort row
    srow = split_h(Rect(grid_rect.x, grid_rect.bottom + m.gap, grid_rect.w, 56), [1, 1, 1, 1.2], gap=m.gap)
    for i, (c, (ar, en, ic)) in enumerate(zip(srow, [("ترتيب", "Sort", "rank"), ("تصفية", "Filter", "search"),
                                                     ("استخدام", "Use", "check"), ("حذف", "Delete", "close")])):
        nodes.append(button(c, f"InvAction{i}", ar, en, pal, m, variant="ghost" if i < 2 else ("danger" if i == 3 else "secondary"),
                            icon=ic, size=m.fs_small + 2))
    # side details
    det = Rect(body.right - 400, body.y + 60 + m.gap, 400, body.h - 60 - m.gap - 80)
    nodes.append(N("panel", "InvDetail", det, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.05),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.4), stroke_w=pal.stroke_w, shadow=True))
    big = min(det.w - 80, 220)
    nodes += slot(Rect(det.cx - big / 2, det.y + 30, big, big), "InvDetailSlot", pal, m, rarity=4, icon="gem")
    nodes.append(T("InvDetailName", Rect(det.x + 20, det.y + 30 + big + 24, det.w - 40, 40), "جوهرة القوة",
                   "Power Gem", size=m.fs_head - 6, align="center", color=pal.text))
    nodes.append(T("InvDetailDesc", Rect(det.x + 28, det.y + 30 + big + 70, det.w - 56, 110),
                   "عنصر نادر جداً يرفع القوة الهجومية.", "A very rare item that boosts attack power.",
                   size=m.fs_small, align="center", color=pal.text_dim))
    nodes.append(button(Rect(det.x + 28, det.bottom - 130, det.w - 56, 60), "EquipButton", "تجهيز", "Equip",
                         pal, m, variant="primary", icon="check"))
    nodes.append(button(Rect(det.x + 28, det.bottom - 62, det.w - 56, 46), "TradeButton", "متاجرة", "Trade",
                         pal, m, variant="ghost", icon="refresh", size=m.fs_small + 1))
    nodes.append(T("InvCount", Rect(win.x + 24, win.bottom - m.footer + 16, 500, 56), "24 / 60 خانة مستخدمة",
                   "24 / 60 slots used", size=m.fs_small, align="left", color=pal.text_dim))
    nodes += progress(Rect(win.x + 540, win.bottom - m.footer + 30, 420, 20), "InvSpace", pal, m, value=0.4)
    return nodes


def build_settings(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="dust", seed=7)]
    win = Rect(m.pad * 0.9, m.pad * 0.75, w - m.pad * 1.8, h - m.pad * 1.5)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="settings")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    side, main = split_h(body, [m.sidebar, 1], gap=m.gap)
    nodes.append(N("panel", "SettingsSide", side, radius=m.radius, top=pal.panel,
                   bottom=mix(pal.panel_lo, (0, 0, 0), 0.15), stroke=pal.stroke, stroke_w=pal.stroke_w - 1))
    cats = [("الصوت", "Audio", "volume"), ("الرسوميات", "Graphics", "eye"), ("التحكم", "Controls", "target"),
            ("الحساب", "Account", "user"), ("اللغة", "Language", "chat")]
    ch = split_v(Rect(side.x + 14, side.y + 18, side.w - 28, side.h - 36), [1] * len(cats), gap=m.gap * 0.7)
    for i, (c, (ar, en, ic)) in enumerate(zip(ch, cats)):
        act = i == 0
        nodes.append(N("tab", f"SetCat{i}", c, active=act, radius=m.radius * 0.7))
        nodes.append(N("icon", f"SetCat{i}Icon", Rect(c.x + 16, c.cy - 18, 36, 36), icon=ic,
                       color=pal.accent_hi if act else pal.text_dim, secondary=mix(pal.accent, (0, 0, 0), 0.4)))
        nodes.append(T(f"SetCat{i}Label", Rect(c.x + 62, c.y, c.w - 72, c.h), ar, en, size=m.fs_body - 3,
                       align="left", color=pal.text if act else pal.text_dim))

    nodes.append(N("panel", "SettingsMain", main, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.04),
                   bottom=mix(pal.panel_lo, (0, 0, 0), 0.1), stroke=pal.stroke, stroke_w=pal.stroke_w - 1))
    inner = main.inset(28)
    nodes.append(T("SettingsHeading", Rect(inner.x, inner.y, inner.w, 44), "الصوت", "Audio",
                   size=m.fs_head - 4, align="left", color=pal.text))
    nodes.append(N("divider", "SettingsLine", Rect(inner.x, inner.y + 52, inner.w, 2), color=pal.stroke))
    rows_rect = Rect(inner.x, inner.y + 72, inner.w, inner.h - 72 - 90)
    rrects = split_v(rows_rect, [1] * 5, gap=m.gap * 0.8)
    labels = [("مستوى الصوت الرئيسي", "Master volume", "slider", 0.7),
              ("المؤثرات الصوتية", "Sound effects", "toggle", 1),
              ("الموسيقى", "Music", "toggle", 0),
              ("صوت الدردشة", "Voice chat", "slider", 0.4),
              ("الاهتزاز", "Vibration", "toggle", 1)]
    for i, (c, (ar, en, kind, val)) in enumerate(zip(rrects, labels)):
        nodes.append(N("panel", f"SetRow{i}", c, radius=m.radius * 0.6,
                       top=mix(pal.panel, (255, 255, 255), 0.05) if i % 2 == 0 else pal.panel,
                       bottom=mix(pal.panel_lo, (0, 0, 0), 0.08), stroke=mix(pal.stroke, pal.panel, 0.6),
                       stroke_w=1))
        nodes.append(T(f"SetRow{i}Label", Rect(c.x + 24, c.y, c.w * 0.5, c.h), ar, en, size=m.fs_body - 2,
                       align="left", color=pal.text))
        if kind == "slider":
            sr = Rect(c.right - 360, c.cy - 10, 300, 20)
            nodes += progress(sr, f"SetSlider{i}", pal, m, value=val, height=20)
            nodes.append(N("knob", f"SetKnob{i}", Rect(sr.x + sr.w * val - 16, sr.cy - 16, 32, 32),
                           color=pal.panel_hi, dot=pal.accent))
            nodes.append(T(f"SetSlider{i}Val", Rect(sr.right + 12, c.y, 60, c.h), f"{int(val*100)}%",
                           f"{int(val*100)}%", size=m.fs_small, align="left", color=pal.text_dim))
        else:
            nodes.append(N("toggle", f"SetToggle{i}", Rect(c.right - 100, c.cy - 20, 76, 40), on=bool(val)))
    nodes.append(button(Rect(inner.x, inner.bottom - 66, 220, 60), "SaveSettings", "حفظ", "Save", pal, m,
                        variant="primary", icon="check"))
    nodes.append(button(Rect(inner.x + 240, inner.bottom - 66, 220, 60), "ResetSettings", "استعادة الافتراضي",
                         "Reset", pal, m, variant="ghost", icon="refresh"))
    return nodes


def build_loading(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="rays", seed=13)]
    nodes.append(N("scrim", "CenterScrim", Rect(0, 0, w, h), alpha=0.35))
    bw = 900
    nodes.append(N("avatar", "LoadLogo", Rect(w / 2 - 90, h * 0.16, 180, 180), ring=pal.accent, crown=False))
    nodes.append(N("icon", "LoadLogoIcon", Rect(w / 2 - 52, h * 0.16 + 38, 104, 104), icon="bolt",
                   color=pal.accent_hi, secondary=mix(pal.accent, (255, 255, 255), 0.5)))
    nodes.append(T("LoadTitle", Rect(w / 2 - bw / 2, h * 0.16 + 200, bw, 90), brief.title, brief.title,
                   size=m.fs_title, align="center", color=pal.text, stroke=mix(pal.bg_deep, (0, 0, 0), 0.7)))
    nodes.append(T("LoadSub", Rect(w / 2 - bw / 2, h * 0.16 + 290, bw, 44), "جارٍ تحميل العالم…",
                   "Loading world...", size=m.fs_head - 6, align="center", color=pal.text_dim))
    pr = Rect(w / 2 - 520, h * 0.62, 1040, 30)
    nodes += progress(pr, "LoadProgress", pal, m, value=0.72, stripes=True, height=30)
    nodes.append(T("LoadPercent", Rect(pr.x, pr.y - 54, pr.w, 40), "72%", "72%", size=m.fs_head - 8,
                   align="center", color=pal.accent_hi))
    nodes.append(T("LoadStep", Rect(pr.x, pr.y + 44, pr.w, 36), "تحميل الخرائط (3/5)", "Loading maps (3/5)",
                   size=m.fs_small, align="center", color=pal.text_dim))
    tips = split_h(Rect(w / 2 - 560, h * 0.78, 1120, 110), [1, 1, 1], gap=m.gap)
    for i, (c, (ar, en, ic)) in enumerate(zip(tips, [("نصيحة: اجمع الجواهر", "Tip: collect gems", "gem"),
                                                    ("نصيحة: انضم لفريق", "Tip: join a team", "user"),
                                                    ("نصيحة: طوّر سلاحك", "Tip: upgrade gear", "bolt")])):
        nodes.append(N("toast", f"Tip{i}", c, color=[pal.accent, pal.accent2, pal.info][i],
                       radius=m.radius, side="left"))
        nodes.append(N("icon", f"Tip{i}Icon", Rect(c.x + 18, c.cy - 20, 40, 40), icon=ic,
                       color=[pal.accent, pal.accent2, pal.info][i]))
        nodes.append(T(f"Tip{i}Label", Rect(c.x + 68, c.y, c.w - 84, c.h), ar, en, size=m.fs_small + 1,
                       align="left", color=pal.text))
    nodes.append(T("LoadFooter", Rect(0, h - 70, w, 40), "Roblox UI Forge — صُممت هذه الواجهة آلياً",
                   "Roblox UI Forge - this UI was generated automatically", size=m.fs_small,
                   align="center", color=pal.text_dim))
    return nodes


def build_leaderboard(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="nebula", seed=17)]
    win = Rect(m.pad * 0.9, m.pad * 0.7, w - m.pad * 1.8, h - m.pad * 1.4)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="trophy")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    nodes += tab_bar(Rect(body.x, body.y, body.w * 0.55, 58), ["اليوم", "الأسبوع", "الكل"],
                     ["Daily", "Weekly", "All time"], pal, m, name="LbTab")
    # podium
    pod = Rect(body.x, body.y + 58 + m.gap, body.w, 250)
    heights = [210, 250, 170]
    order = [1, 0, 2]
    names = [("Nova_King", "Nova_King", "184,200"), ("ShadowFox", "ShadowFox", "171,940"), ("RBLX_Pro", "RBLX_Pro", "160,010")]
    cells = split_h(pod, [1, 1.15, 1], gap=m.gap)
    for pos, idx in zip(cells, order):
        ar, en, score = names[idx]
        ph = heights[idx]
        c = Rect(pos.x, pos.bottom - ph, pos.w, ph)
        col = [pal.warn, pal.text_dim, mix(pal.warn, (120, 60, 20), 0.35)][idx]
        nodes.append(N("panel", f"Podium{idx}", c, radius=m.radius, top=mix(pal.panel_hi, col, 0.22),
                       bottom=mix(pal.panel_lo, col, 0.12), stroke=mix(pal.stroke, col, 0.6),
                       stroke_w=pal.stroke_w + 1, shadow=True))
        nodes.append(N("avatar", f"Podium{idx}Avatar", Rect(c.cx - 46, c.y + 22, 92, 92), ring=col, crown=idx == 0))
        nodes.append(N("badge", f"Podium{idx}Medal", Rect(c.cx - 26, c.y + 6, 52, 40), color=col, radius=12))
        nodes.append(T(f"Podium{idx}MedalLabel", Rect(c.cx - 26, c.y + 6, 52, 40), str(idx + 1), str(idx + 1),
                       size=m.fs_body - 2, align="center", color=mix(col, (0, 0, 0), 0.6)))
        nodes.append(T(f"Podium{idx}Name", Rect(c.x + 10, c.y + 124, c.w - 20, 40), ar, en,
                       size=m.fs_body, align="center", color=pal.text))
        nodes.append(T(f"Podium{idx}Score", Rect(c.x + 10, c.y + 164, c.w - 20, 36), score, score,
                       size=m.fs_small + 2, align="center", color=pal.accent_hi))
    # list
    list_rect = Rect(body.x, pod.bottom + m.gap, body.w, body.h - (pod.bottom - body.y) - m.gap - 84)
    rows = split_v(list_rect, [1] * 5, gap=m.gap * 0.6)
    data = [("Blaze_99", "Blaze_99", "مستوى 51", "Level 51", "142,300"),
            ("Mighty_Omar", "Mighty_Omar", "مستوى 48", "Level 48", "138,770"),
            ("ZezoPlayz", "ZezoPlayz", "مستوى 44", "Level 44", "121,005"),
            ("Luna_Star", "Luna_Star", "مستوى 39", "Level 39", "110,420"),
            ("You", "You", "مستوى 42", "Level 42", "98,110")]
    for i, (c, (ar, en, ma, men, sc)) in enumerate(zip(rows, data)):
        nodes += row(c, f"LbRow{i}", i + 3, ar, en, ma, men, pal, m, icon="user",
                     highlight=(i == 4), right=sc)
    nodes.append(button(Rect(body.right - 260, body.bottom - 60, 260, 58), "RefreshLb", "تحديث", "Refresh",
                        pal, m, variant="secondary", icon="refresh", size=m.fs_small + 3))
    nodes.append(T("LbHint", Rect(body.x, body.bottom - 52, 600, 44), "يُحدَّث الترتيب كل 5 دقائق",
                   "Rankings refresh every 5 minutes", size=m.fs_small, align="left", color=pal.text_dim))
    return nodes


def build_profile(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="aurora", seed=21)]
    win = Rect(m.pad * 0.9, m.pad * 0.75, w - m.pad * 1.8, h - m.pad * 1.5)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="user")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    left, right = split_h(body, [0.85, 1.15], gap=m.gap)
    nodes.append(N("panel", "ProfileCard", left, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.06),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.4), stroke_w=pal.stroke_w + 1,
                   shadow=True))
    av = 200
    nodes.append(N("avatar", "ProfileAvatar", Rect(left.cx - av / 2, left.y + 40, av, av), ring=pal.accent, crown=True))
    nodes.append(T("ProfileName", Rect(left.x, left.y + 40 + av + 12, left.w, 48), "Player_01", "Player_01",
                   size=m.fs_head, align="center", color=pal.text))
    nodes.append(T("ProfileTag", Rect(left.x, left.y + 40 + av + 62, left.w, 34), "@player01 • انضم 2023",
                   "@player01 - joined 2023", size=m.fs_small, align="center", color=pal.text_dim))
    chips = [("أسطوري", "Legend", pal.warn), ("محارب", "Warrior", pal.danger), ("VIP", "VIP", pal.accent)]
    chx = left.cx - (len(chips) * 130 + (len(chips) - 1) * 14) / 2
    for i, (ar, en, col) in enumerate(chips):
        c = Rect(chx + i * 144, left.y + 40 + av + 104, 130, 42)
        nodes.append(N("badge", f"ProfileChip{i}", c, color=mix(col, pal.panel_lo, 0.25), radius=21,
                       stroke=col, stroke_w=1))
        nodes.append(T(f"ProfileChip{i}Label", c, ar, en, size=m.fs_small, align="center", color=pal.text))
    nodes.append(T("ProfileXPLabel", Rect(left.x + 40, left.y + 40 + av + 168, left.w - 80, 32),
                   "التقدم للمستوى 43", "Progress to level 43", size=m.fs_small, align="left", color=pal.text_dim))
    nodes += progress(Rect(left.x + 40, left.y + 40 + av + 200, left.w - 80, 24), "ProfileXP", pal, m,
                      value=0.68, stripes=True, height=24, label="6,800 / 10,000", label_en="6,800 / 10,000")
    bts = split_h(Rect(left.x + 40, left.bottom - 92, left.w - 80, 62), [1, 1, 1], gap=m.gap)
    for i, (c, (ar, en, ic, var)) in enumerate(zip(bts, [("تعديل", "Edit", "settings", "secondary"),
                                                         ("مشاركة", "Share", "chat", "secondary"),
                                                         ("خروج", "Logout", "logout", "danger")])):
        nodes.append(button(c, f"ProfileBtn{i}", ar, en, pal, m, variant=var, icon=ic, size=m.fs_small + 2))

    nodes.append(N("panel", "StatsPanel", right, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.05),
                   bottom=mix(pal.panel_lo, (0, 0, 0), 0.1), stroke=pal.stroke, stroke_w=pal.stroke_w, shadow=True))
    inner = right.inset(28)
    nodes.append(T("StatsHeading", Rect(inner.x, inner.y, inner.w, 40), "الإحصائيات", "Statistics",
                   size=m.fs_head - 4, align="left", color=pal.text))
    nodes.append(N("divider", "StatsLine", Rect(inner.x, inner.y + 48, inner.w, 2), color=pal.stroke))
    cells = grid(Rect(inner.x, inner.y + 68, inner.w, inner.h - 68 - 260), 2, 3, gap=m.gap)
    vals = [("1,284", "الفوز", "Wins", "trophy", pal.success), ("327", "الخسارة", "Losses", "target", pal.danger),
            ("4.2", "نسبة K/D", "K/D ratio", "bolt", pal.accent), ("58", "الإنجازات", "Badges", "medal", pal.warn),
            ("92h", "وقت اللعب", "Play time", "star", pal.info), ("#12", "الترتيب", "Global rank", "rank", pal.accent2)]
    for c, (v, ar, en, ic, col) in zip(cells, vals):
        nodes += stat_card(c, f"Stat{en.replace(' ', '')}", v, ar, en, ic, pal, m, color=col)
    nodes.append(T("ActivityHeading", Rect(inner.x, inner.bottom - 236, inner.w, 34), "آخر النشاطات",
                   "Recent activity", size=m.fs_body - 2, align="left", color=pal.text))
    acts = split_v(Rect(inner.x, inner.bottom - 196, inner.w, 196), [1] * 3, gap=m.gap * 0.5)
    for i, (c, (ar, en, ic)) in enumerate(zip(acts, [("فاز في معركة الفرق", "Won a team battle", "trophy"),
                                                     ("حصل على جوهرة نادرة", "Got a rare gem", "gem"),
                                                     ("صعد إلى المستوى 42", "Reached level 42", "xp")])):
        nodes.append(N("row", f"Act{i}", c, index=i, radius=m.radius * 0.6))
        nodes.append(N("icon", f"Act{i}Icon", Rect(c.x + 16, c.cy - 18, 36, 36), icon=ic,
                       color=pal.accent_hi, secondary=mix(pal.accent, (0, 0, 0), 0.4)))
        nodes.append(T(f"Act{i}Label", Rect(c.x + 64, c.y, c.w - 200, c.h), ar, en, size=m.fs_body - 4,
                       align="left", color=pal.text))
        nodes.append(T(f"Act{i}Time", Rect(c.right - 180, c.y, 164, c.h), "منذ ساعتين", "2h ago",
                       size=m.fs_small, align="right", color=pal.text_dim))
    return nodes


def build_hud(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="dust", seed=31)]
    nodes.append(N("scrim", "HudScrim", Rect(0, h - 320, w, 320), alpha=0.35))
    # top-left player chip
    chip = Rect(m.pad, m.pad, 340, 78)
    nodes.append(N("badge", "PlayerChip", chip, color=mix(pal.panel_lo, (0, 0, 0), 0.35), radius=chip.h / 2,
                   stroke=mix(pal.stroke, pal.accent, 0.4), stroke_w=pal.stroke_w))
    nodes.append(N("avatar", "HudAvatar", Rect(chip.x + 8, chip.cy - 31, 62, 62), ring=pal.accent))
    nodes.append(T("HudName", Rect(chip.x + 82, chip.y + 10, chip.w - 96, 34), "Player_01", "Player_01",
                   size=m.fs_body - 4, align="left", color=pal.text))
    nodes.append(T("HudLevel", Rect(chip.x + 82, chip.y + 40, chip.w - 96, 30), "المستوى 42", "Level 42",
                   size=m.fs_small - 3, align="left", color=pal.text_dim))
    # top-center compass
    comp = Rect(w / 2 - 320, m.pad, 640, 54)
    nodes.append(N("badge", "Compass", comp, color=mix(pal.panel_lo, (0, 0, 0), 0.45), radius=27,
                   stroke=mix(pal.stroke, pal.accent, 0.35), stroke_w=1))
    for i, d in enumerate(["W", "NW", "N", "NE", "E"]):
        nodes.append(T(f"Compass{i}", Rect(comp.x + 60 + i * 130, comp.y, 120, comp.h), d, d,
                       size=m.fs_small, align="center", color=pal.accent_hi if i == 2 else pal.text_dim))
    # top-right minimap
    mm = 250
    nodes.append(N("minimap", "Minimap", Rect(w - m.pad - mm, m.pad, mm, mm), radius=m.radius))
    nodes.append(T("MinimapLabel", Rect(w - m.pad - mm, m.pad + mm + 6, mm, 30), "الخريطة", "Map",
                   size=m.fs_small - 3, align="center", color=pal.text_dim))
    # killfeed
    kf = split_v(Rect(w - m.pad - 420, m.pad + mm + 50, 420, 180), [1] * 3, gap=8)
    for i, (c, msg) in enumerate(zip(kf, [("Player_01 قتل ShadowFox", "Player_01 eliminated ShadowFox"),
                                          ("Nova_King فاز بالجولة", "Nova_King won the round"),
                                          ("Blaze_99 انضم للعبة", "Blaze_99 joined the game")])):
        nodes.append(N("toast", f"Kill{i}", c, color=[pal.danger, pal.warn, pal.info][i], radius=m.radius * 0.7,
                       side="right"))
        nodes.append(T(f"Kill{i}Label", Rect(c.x + 18, c.y, c.w - 36, c.h), msg, msg, size=m.fs_small - 1,
                       align="center", color=pal.text))
    # bottom-left health + armor
    bars = Rect(m.pad, h - m.pad - 150, 560, 150)
    nodes.append(N("icon", "HealthIcon", Rect(bars.x, bars.y + 6, 44, 44), icon="heart", color=pal.danger,
                   secondary=mix(pal.danger, (0, 0, 0), 0.4)))
    nodes += progress(Rect(bars.x + 58, bars.y + 12, bars.w - 58, 34), "Health", pal, m, value=0.78,
                      color=pal.danger, height=34, label="78 / 100", label_en="78 / 100")
    nodes.append(N("icon", "ArmorIcon", Rect(bars.x, bars.y + 74, 44, 44), icon="shield", color=pal.info,
                   secondary=mix(pal.info, (0, 0, 0), 0.4)))
    nodes += progress(Rect(bars.x + 58, bars.y + 80, bars.w - 58, 26), "Armor", pal, m, value=0.45,
                      color=pal.info, height=26, label="45", label_en="45")
    # bottom-right ammo
    ammo = Rect(w - m.pad - 340, h - m.pad - 130, 340, 130)
    nodes.append(N("panel", "AmmoPanel", ammo, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.06),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.4), stroke_w=pal.stroke_w, shadow=True))
    nodes.append(N("icon", "AmmoIcon", Rect(ammo.x + 22, ammo.cy - 28, 56, 56), icon="ammo",
                   color=pal.accent_hi, secondary=mix(pal.accent, (0, 0, 0), 0.4)))
    nodes.append(T("AmmoCount", Rect(ammo.x + 92, ammo.y + 16, ammo.w - 110, 60), "24", "24",
                   size=m.fs_title - 12, align="left", color=pal.text))
    nodes.append(T("AmmoMax", Rect(ammo.x + 92, ammo.y + 78, ammo.w - 110, 34), "/ 120 طلقة", "/ 120 rounds",
                   size=m.fs_small, align="left", color=pal.text_dim))
    # hotbar
    hb = grid(Rect(w / 2 - 330, h - m.pad - 110, 660, 100), 5, 1, gap=m.gap * 0.8, cell_ratio=1.0)
    for i, c in enumerate(hb):
        nodes += slot(c, f"Hotbar{i}", pal, m, rarity=i % 3, icon=["sword", "shield", "gem", "fire", "star"][i],
                      selected=(i == 0))
        nodes.append(N("badge", f"Hotbar{i}Num", Rect(c.x + 6, c.y + 6, 30, 30), color=mix(pal.bg_deep, (0, 0, 0), 0.4),
                       radius=8, stroke=pal.stroke, stroke_w=1))
        nodes.append(T(f"Hotbar{i}NumLabel", Rect(c.x + 6, c.y + 6, 30, 30), str(i + 1), str(i + 1),
                       size=m.fs_small - 4, align="center", color=pal.text))
    # objective
    obj = Rect(w / 2 - 240, m.pad + 66, 480, 56)
    nodes.append(N("badge", "Objective", obj, color=mix(pal.panel_lo, (0, 0, 0), 0.4), radius=28,
                   stroke=mix(pal.stroke, pal.accent, 0.35), stroke_w=1))
    nodes.append(T("ObjectiveLabel", obj, "الهدف: اجمع 5 جواهر", "Objective: collect 5 gems",
                   size=m.fs_small + 1, align="center", color=pal.text, icon="flag"))
    return nodes


def build_pause(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="nebula", seed=41)]
    nodes.append(N("scrim", "PauseScrim", Rect(0, 0, w, h), alpha=0.6))
    pw, phh = 620, 620
    panel = center_in(Rect(0, 0, w, h), pw, phh)
    nodes.append(N("panel", "PausePanel", panel, radius=m.radius + 6, top=mix(pal.panel_hi, (255, 255, 255), 0.07),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.5), stroke_w=pal.stroke_w + 1,
                   shadow=True))
    nodes.append(T("PauseTitle", Rect(panel.x, panel.y + 48, panel.w, 70), brief.title or "إيقاف مؤقت",
                   brief.title or "Paused", size=m.fs_title - 12, align="center", color=pal.text))
    nodes.append(N("divider", "PauseLine", Rect(panel.cx - 100, panel.y + 130, 200, 3), color=pal.accent))
    labels = [("استئناف", "Resume", "play", "primary"), ("الإعدادات", "Settings", "settings", "secondary"),
              ("المتجر", "Shop", "cart", "secondary"), ("الخروج", "Quit", "logout", "danger")]
    cells = split_v(Rect(panel.x + 70, panel.y + 170, panel.w - 140, panel.h - 240), [1] * len(labels), gap=m.gap)
    for i, (c, (ar, en, ic, var)) in enumerate(zip(cells, labels)):
        nodes.append(button(c, f"PauseBtn{i}", ar, en, pal, m, variant=var, icon=ic))
    nodes.append(T("PauseHint", Rect(panel.x, panel.bottom - 62, panel.w, 34), "اضغط ESC للمتابعة",
                   "Press ESC to resume", size=m.fs_small, align="center", color=pal.text_dim))
    return nodes


def build_login(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="aurora", seed=53)]
    nodes.append(N("scrim", "LoginScrim", Rect(0, 0, w, h), alpha=0.45))
    pw, phh = 640, 700
    panel = center_in(Rect(0, 0, w, h), pw, phh)
    nodes.append(N("panel", "LoginPanel", panel, radius=m.radius + 6, top=mix(pal.panel_hi, (255, 255, 255), 0.07),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.5), stroke_w=pal.stroke_w + 1,
                   shadow=True))
    nodes.append(N("avatar", "LoginLogo", Rect(panel.cx - 60, panel.y + 40, 120, 120), ring=pal.accent))
    nodes.append(N("icon", "LoginLogoIcon", Rect(panel.cx - 34, panel.y + 66, 68, 68), icon="key",
                   color=pal.accent_hi, secondary=mix(pal.accent, (255, 255, 255), 0.5)))
    nodes.append(T("LoginTitle", Rect(panel.x, panel.y + 176, panel.w, 56), brief.title or "تسجيل الدخول",
                   brief.title or "Sign in", size=m.fs_head + 4, align="center", color=pal.text))
    nodes.append(T("LoginSub", Rect(panel.x, panel.y + 232, panel.w, 34), "أدخل بياناتك للمتابعة",
                   "Enter your credentials to continue", size=m.fs_small, align="center", color=pal.text_dim))
    fields = [("اسم المستخدم", "Username", "user", False), ("كلمة المرور", "Password", "lock", True)]
    fy = panel.y + 288
    for i, (ar, en, ic, focus) in enumerate(fields):
        fr = Rect(panel.x + 70, fy + i * 100, panel.w - 140, 76)
        nodes.append(N("field", f"LoginField{i}", fr, radius=m.radius, focus=focus))
        nodes.append(N("icon", f"LoginField{i}Icon", Rect(fr.x + 22, fr.cy - 20, 40, 40), icon=ic,
                       color=pal.accent_hi if focus else pal.text_dim, secondary=mix(pal.accent, (0, 0, 0), 0.4)))
        nodes.append(T(f"LoginField{i}Placeholder", Rect(fr.x + 76, fr.y, fr.w - 96, fr.h), ar, en,
                       size=m.fs_body - 2, align="left", color=pal.text if focus else pal.text_dim))
    tr = Rect(panel.x + 70, fy + 210, 260, 44)
    nodes.append(N("toggle", "RememberToggle", Rect(tr.x, tr.y, 76, 40), on=True))
    nodes.append(T("RememberLabel", Rect(tr.x + 92, tr.y, tr.w - 92, tr.h), "تذكرني", "Remember me",
                   size=m.fs_body - 4, align="left", color=pal.text_dim))
    nodes.append(T("ForgotLabel", Rect(panel.right - 250, fy + 210, 180, 44), "نسيت كلمة المرور؟",
                   "Forgot password?", size=m.fs_body - 4, align="right", color=pal.accent_hi))
    nodes.append(button(Rect(panel.x + 70, fy + 276, panel.w - 140, 78), "LoginButton", "دخول", "Sign in",
                        pal, m, variant="primary", icon="play"))
    nodes.append(button(Rect(panel.x + 70, fy + 366, panel.w - 140, 62), "GuestButton", "الدخول كزائر",
                        "Continue as guest", pal, m, variant="ghost", icon="user"))
    nodes.append(N("divider", "LoginLine", Rect(panel.x + 70, panel.bottom - 78, panel.w - 140, 2), color=pal.stroke))
    nodes.append(T("LoginFooter", Rect(panel.x, panel.bottom - 66, panel.w, 34), "ليس لديك حساب؟ سجّل الآن",
                   "No account? Sign up", size=m.fs_small, align="center", color=pal.text_dim))
    return nodes


def build_crate(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="burst", seed=61)]
    win = Rect(m.pad * 0.9, m.pad * 0.7, w - m.pad * 1.8, h - m.pad * 1.4)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="gift")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    left, right = split_h(body, [1.1, 0.9], gap=m.gap)
    nodes.append(N("panel", "CratePanel", left, radius=m.radius, top=mix(pal.panel_hi, pal.accent, 0.12),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.5), stroke_w=pal.stroke_w + 1,
                   shadow=True))
    big = min(left.w - 160, 340)
    nodes.append(N("slot", "CrateSlot", Rect(left.cx - big / 2, left.y + 46, big, big), rarity=4,
                   rarity_color=pal.warn, radius=m.radius * 1.2, selected=True))
    nodes.append(N("icon", "CrateIcon", Rect(left.cx - big * 0.28, left.y + 46 + big * 0.22, big * 0.56, big * 0.56),
                   icon="gift", color=mix(pal.warn, (255, 255, 255), 0.25), secondary=mix(pal.warn, (0, 0, 0), 0.4)))
    nodes.append(T("CrateName", Rect(left.x, left.y + 46 + big + 16, left.w, 46), "الصندوق الذهبي",
                   "Golden Crate", size=m.fs_head, align="center", color=pal.text))
    nodes.append(T("CrateDesc", Rect(left.x + 40, left.y + 46 + big + 66, left.w - 80, 60),
                   "يحتوي على عنصر نادر واحد على الأقل", "Contains at least one rare item",
                   size=m.fs_small + 1, align="center", color=pal.text_dim))
    nodes += progress(Rect(left.x + 60, left.bottom - 190, left.w - 120, 26), "CrateOdds", pal, m,
                      value=0.35, color=pal.warn, height=26, label="فرصة الأسطوري 3.5%", label_en="3.5% legendary chance")
    nodes.append(button(Rect(left.x + 60, left.bottom - 150, left.w - 120, 76), "OpenCrate", "افتح بـ 250 جوهرة",
                        "Open for 250 gems", pal, m, variant="primary", icon="key"))
    nodes.append(button(Rect(left.x + 60, left.bottom - 66, left.w - 120, 54), "Open10", "افتح 10 بـ 2,250",
                        "Open 10 for 2,250", pal, m, variant="secondary", icon="bolt", size=m.fs_small + 2))

    nodes.append(N("panel", "CrateSide", right, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.05),
                   bottom=mix(pal.panel_lo, (0, 0, 0), 0.1), stroke=pal.stroke, stroke_w=pal.stroke_w))
    inner = right.inset(24)
    nodes.append(T("CrateSideHeading", Rect(inner.x, inner.y, inner.w, 40), "المحتويات المحتملة",
                   "Possible contents", size=m.fs_head - 6, align="left", color=pal.text))
    nodes.append(N("divider", "CrateSideLine", Rect(inner.x, inner.y + 46, inner.w, 2), color=pal.stroke))
    cells = grid(Rect(inner.x, inner.y + 62, inner.w, inner.h - 62 - 40), 3, 3, gap=m.gap, cell_ratio=1.0)
    for i, (c, (ic, rar)) in enumerate(zip(cells, [("sword", 3), ("shield", 2), ("gem", 4), ("heart", 1),
                                                   ("star", 2), ("key", 0), ("crown", 4), ("fire", 3), ("gift", 1)])):
        nodes += slot(c, f"Reward{i}", pal, m, rarity=rar, icon=ic)
    nodes += currency_pill(Rect(right.x + 24, right.bottom - 60, 160, 48), "320", "gem", pal, m, "CrateGems")
    nodes.append(T("CrateSideHint", Rect(right.x + 200, right.bottom - 56, right.w - 220, 40),
                   "آخر فتح: منذ 3 دقائق", "Last opened 3 minutes ago", size=m.fs_small - 2,
                   align="left", color=pal.text_dim))
    return nodes


def build_quests(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="glow", seed=71)]
    win = Rect(m.pad * 0.9, m.pad * 0.7, w - m.pad * 1.8, h - m.pad * 1.4)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="flag")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    left, right = split_h(body, [1.15, 0.85], gap=m.gap)
    nodes += tab_bar(Rect(left.x, left.y, left.w, 56), ["نشطة", "منتهية", "يومية"],
                     ["Active", "Completed", "Daily"], pal, m, name="QuestTab")
    qrect = Rect(left.x, left.y + 56 + m.gap, left.w, left.h - 56 - m.gap)
    quests = [("اجمع 10 جواهر", "Collect 10 gems", "6 / 10", 0.6, "gem"),
              ("اهزم 5 أعداء", "Defeat 5 enemies", "5 / 5", 1.0, "sword"),
              ("العب 3 مباريات", "Play 3 matches", "1 / 3", 0.33, "play"),
              ("طور سلاحاً", "Upgrade a weapon", "0 / 1", 0.0, "bolt"),
              ("ادعُ صديقاً", "Invite a friend", "2 / 3", 0.66, "user")]
    cells = split_v(qrect, [1] * len(quests), gap=m.gap * 0.7)
    for i, (c, (ar, en, pr, val, ic)) in enumerate(zip(cells, quests)):
        done = val >= 1
        nodes.append(N("row", f"Quest{i}", c, index=i, radius=m.radius * 0.7, highlight=done))
        nodes.append(N("icon", f"Quest{i}Icon", Rect(c.x + 18, c.cy - 22, 44, 44), icon=ic,
                       color=pal.success if done else pal.accent_hi, secondary=mix(pal.accent, (0, 0, 0), 0.4)))
        nodes.append(T(f"Quest{i}Title", Rect(c.x + 78, c.y + 10, c.w - 260, 36), ar, en, size=m.fs_body - 2,
                       align="left", color=pal.text))
        nodes.append(T(f"Quest{i}Prog", Rect(c.x + 78, c.y + 46, c.w - 260, 30), pr, pr, size=m.fs_small,
                       align="left", color=pal.text_dim))
        nodes += progress(Rect(c.x + 78, c.y + c.h - 26, c.w - 340, 14), f"Quest{i}Bar", pal, m, value=val,
                          color=pal.success if done else pal.accent, height=14)
        nodes.append(button(Rect(c.right - 236, c.cy - 26, 216, 52), f"Quest{i}Btn",
                            "استلام", "Claim", pal, m, variant="success" if done else "ghost",
                            icon="gift" if done else "lock", size=m.fs_small + 1))
    nodes.append(N("panel", "QuestSide", right, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.05),
                   bottom=mix(pal.panel_lo, (0, 0, 0), 0.1), stroke=pal.stroke, stroke_w=pal.stroke_w, shadow=True))
    inner = right.inset(26)
    nodes.append(T("QuestSideHeading", Rect(inner.x, inner.y, inner.w, 40), "مكافآت اليوم", "Today's rewards",
                   size=m.fs_head - 6, align="left", color=pal.text))
    nodes.append(N("divider", "QuestSideLine", Rect(inner.x, inner.y + 46, inner.w, 2), color=pal.stroke))
    cells = grid(Rect(inner.x, inner.y + 62, inner.w, inner.h - 62 - 200), 2, 3, gap=m.gap, cell_ratio=1.0)
    for i, (c, (ic, rar)) in enumerate(zip(cells, [("coin", 1), ("gem", 3), ("star", 2), ("gift", 4),
                                                   ("key", 1), ("crown", 4)])):
        nodes += slot(c, f"QuestReward{i}", pal, m, rarity=rar, icon=ic)
    nodes.append(T("QuestSideInfo", Rect(inner.x, inner.bottom - 176, inner.w, 100),
                   "أكمل 3 مهام يومية لتحصل على صندوق إضافي.", "Complete 3 daily quests to earn a bonus crate.",
                   size=m.fs_small, align="left", color=pal.text_dim))
    nodes.append(button(Rect(inner.x, inner.bottom - 66, inner.w, 60), "QuestClaimAll", "استلام الكل",
                        "Claim all", pal, m, variant="primary", icon="check"))
    return nodes


def build_dialog(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="dust", seed=83)]
    nodes.append(N("scrim", "DialogScrim", Rect(0, 0, w, h), alpha=0.62))
    pw, phh = 720, 380
    panel = center_in(Rect(0, 0, w, h), pw, phh)
    nodes.append(N("panel", "DialogPanel", panel, radius=m.radius + 4, top=mix(pal.panel_hi, (255, 255, 255), 0.07),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.5), stroke_w=pal.stroke_w + 1,
                   shadow=True))
    nodes.append(N("icon", "DialogIcon", Rect(panel.cx - 40, panel.y + 34, 80, 80), icon="bolt",
                   color=pal.warn, secondary=mix(pal.warn, (0, 0, 0), 0.4)))
    nodes.append(T("DialogTitle", Rect(panel.x + 40, panel.y + 128, panel.w - 80, 52), "تأكيد الخروج",
                   "Confirm exit", size=m.fs_head, align="center", color=pal.text))
    nodes.append(T("DialogBody", Rect(panel.x + 60, panel.y + 184, panel.w - 120, 90),
                   "سيتم حفظ تقدمك تلقائياً قبل الخروج. هل تريد المتابعة؟",
                   "Your progress is saved automatically. Continue?", size=m.fs_body - 2,
                   align="center", color=pal.text_dim))
    cells = split_h(Rect(panel.x + 60, panel.bottom - 92, panel.w - 120, 64), [1, 1], gap=m.gap)
    nodes.append(button(cells[0], "DialogCancel", "إلغاء", "Cancel", pal, m, variant="ghost", icon="close"))
    nodes.append(button(cells[1], "DialogConfirm", "تأكيد", "Confirm", pal, m, variant="primary", icon="check"))
    # secondary toast for context
    t = Rect(w - m.pad - 380, m.pad, 380, 96)
    nodes.append(N("toast", "DialogToast", t, color=pal.info, radius=m.radius, side="left", shadow=True))
    nodes.append(N("icon", "DialogToastIcon", Rect(t.x + 18, t.cy - 20, 40, 40), icon="bell", color=pal.info))
    nodes.append(T("DialogToastTitle", Rect(t.x + 70, t.y + 12, t.w - 88, 34), "إشعار", "Notice",
                   size=m.fs_body - 4, align="left", color=pal.text))
    nodes.append(T("DialogToastBody", Rect(t.x + 70, t.y + 48, t.w - 88, 32), "تم الحفظ تلقائياً",
                   "Auto-saved", size=m.fs_small - 1, align="left", color=pal.text_dim))
    return nodes


def build_wheel(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="rays", seed=97)]
    win = Rect(m.pad * 0.9, m.pad * 0.7, w - m.pad * 1.8, h - m.pad * 1.4)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="star")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    left, right = split_h(body, [1, 0.7], gap=m.gap)
    nodes.append(N("panel", "WheelPanel", left, radius=m.radius, top=mix(pal.panel_hi, pal.accent, 0.1),
                   bottom=pal.panel_lo, stroke=mix(pal.stroke, pal.accent, 0.5), stroke_w=pal.stroke_w + 1,
                   shadow=True))
    size = min(left.w - 120, left.h - 240)
    nodes.append(N("wheel", "SpinWheel", Rect(left.cx - size / 2, left.y + 40, size, size), segments=10))
    nodes.append(button(Rect(left.cx - 180, left.bottom - 130, 360, 74), "SpinButton", "أدر العجلة",
                        "Spin the wheel", pal, m, variant="primary", icon="refresh"))
    nodes.append(T("SpinHint", Rect(left.x, left.bottom - 48, left.w, 32), "دورة مجانية كل 4 ساعات",
                   "One free spin every 4 hours", size=m.fs_small, align="center", color=pal.text_dim))
    nodes.append(N("panel", "WheelSide", right, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.05),
                   bottom=mix(pal.panel_lo, (0, 0, 0), 0.1), stroke=pal.stroke, stroke_w=pal.stroke_w))
    inner = right.inset(24)
    nodes.append(T("WheelSideHeading", Rect(inner.x, inner.y, inner.w, 40), "الجوائز", "Prizes",
                   size=m.fs_head - 6, align="left", color=pal.text))
    nodes.append(N("divider", "WheelSideLine", Rect(inner.x, inner.y + 46, inner.w, 2), color=pal.stroke))
    prizes = [("1,000 عملة", "1,000 coins", "coin", 1), ("50 جوهرة", "50 gems", "gem", 2),
              ("صندوق نادر", "Rare crate", "gift", 3), ("أسطوري!", "Legendary!", "crown", 4),
              ("250 عملة", "250 coins", "coin", 0), ("مفتاح", "Key", "key", 2)]
    cells = split_v(Rect(inner.x, inner.y + 62, inner.w, inner.h - 62 - 70), [1] * len(prizes), gap=m.gap * 0.6)
    for i, (c, (ar, en, ic, rar)) in enumerate(zip(cells, prizes)):
        nodes.append(N("row", f"Prize{i}", c, index=i, radius=m.radius * 0.6))
        nodes.append(N("icon", f"Prize{i}Icon", Rect(c.x + 16, c.cy - 20, 40, 40), icon=ic,
                       color=pal.rarity(rar), secondary=mix(pal.rarity(rar), (0, 0, 0), 0.4)))
        nodes.append(T(f"Prize{i}Label", Rect(c.x + 70, c.y, c.w - 160, c.h), ar, en, size=m.fs_body - 3,
                       align="left", color=pal.text))
        nodes.append(N("badge", f"Prize{i}Odds", Rect(c.right - 96, c.cy - 17, 80, 34),
                       color=mix(pal.panel_lo, (0, 0, 0), 0.3), radius=17, stroke=pal.stroke, stroke_w=1))
        nodes.append(T(f"Prize{i}OddsLabel", Rect(c.right - 96, c.cy - 17, 80, 34),
                       f"{[40, 25, 15, 3, 12, 5][i]}%", f"{[40, 25, 15, 3, 12, 5][i]}%",
                       size=m.fs_small - 3, align="center", color=pal.text_dim))
    nodes.append(button(Rect(inner.x, inner.bottom - 60, inner.w, 56), "Spin10Button", "10 دورات بـ 900",
                        "10 spins for 900", pal, m, variant="secondary", icon="bolt", size=m.fs_small + 2))
    return nodes


def build_chat(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="grid", seed=101)]
    win = Rect(m.pad * 1.2, m.pad * 0.8, w - m.pad * 2.4, h - m.pad * 1.6)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="chat")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    side, main = split_h(body, [260, 1], gap=m.gap)
    nodes.append(N("panel", "ChatSide", side, radius=m.radius, top=pal.panel,
                   bottom=mix(pal.panel_lo, (0, 0, 0), 0.15), stroke=pal.stroke, stroke_w=pal.stroke_w - 1))
    rooms = [("عام", "General", 12), ("فريقي", "Team", 4), ("تجارة", "Trade", 38), ("مساعدة", "Help", 7)]
    ch = split_v(Rect(side.x + 14, side.y + 18, side.w - 28, side.h - 36), [1] * len(rooms), gap=m.gap * 0.7)
    for i, (c, (ar, en, n)) in enumerate(zip(ch, rooms)):
        act = i == 0
        nodes.append(N("tab", f"Room{i}", c, active=act, radius=m.radius * 0.7))
        nodes.append(T(f"Room{i}Label", Rect(c.x + 20, c.y, c.w - 76, c.h), ar, en, size=m.fs_body - 3,
                       align="left", color=pal.text if act else pal.text_dim))
        nodes.append(N("badge", f"Room{i}Count", Rect(c.right - 58, c.cy - 16, 44, 32),
                       color=pal.accent if act else mix(pal.panel_lo, (0, 0, 0), 0.3), radius=16))
        nodes.append(T(f"Room{i}CountLabel", Rect(c.right - 58, c.cy - 16, 44, 32), str(n), str(n),
                       size=m.fs_small - 4, align="center", color=(255, 255, 255) if act else pal.text_dim))
    nodes.append(N("panel", "ChatMain", main, radius=m.radius, top=mix(pal.panel_hi, (255, 255, 255), 0.04),
                   bottom=mix(pal.panel_lo, (0, 0, 0), 0.12), stroke=pal.stroke, stroke_w=pal.stroke_w - 1))
    msgs = [("Nova_King", "أهلاً بالجميع!", "Hey everyone!", pal.accent),
            ("ShadowFox", "من يريد فريق؟", "Anyone up for a team?", pal.info),
            ("Player_01", "أنا جاهز 👍", "I'm ready", pal.success),
            ("Blaze_99", "الفوز قريب!", "Victory is close!", pal.warn)]
    inner = main.inset(24)
    cells = split_v(Rect(inner.x, inner.y, inner.w, inner.h - 100), [1] * len(msgs), gap=m.gap * 0.6)
    for i, (c, (who, ar, en, col)) in enumerate(zip(cells, msgs)):
        mine = who == "Player_01"
        bw = c.w * 0.62
        bx = c.right - bw if mine else c.x + 76
        nodes.append(N("avatar", f"Msg{i}Avatar", Rect(c.x + 6, c.y + 6, 56, 56),
                       ring=col, crown=False))
        nodes.append(N("panel", f"Msg{i}Bubble", Rect(bx, c.y + 4, bw, c.h - 8), radius=m.radius * 0.8,
                       top=mix(pal.panel_hi, col, 0.22) if mine else mix(pal.panel_hi, (255, 255, 255), 0.04),
                       bottom=mix(pal.panel_lo, col, 0.1) if mine else pal.panel_lo,
                       stroke=mix(pal.stroke, col, 0.4), stroke_w=1))
        nodes.append(T(f"Msg{i}Who", Rect(bx + 18, c.y + 8, bw - 36, 30), who, who, size=m.fs_small,
                       align="left", color=col))
        nodes.append(T(f"Msg{i}Text", Rect(bx + 18, c.y + 38, bw - 36, c.h - 50), ar, en, size=m.fs_body - 4,
                       align="left", color=pal.text))
    inp = Rect(inner.x, inner.bottom - 76, inner.w - 150, 76)
    nodes.append(N("field", "ChatInput", inp, radius=inp.h / 2))
    nodes.append(N("icon", "ChatInputIcon", Rect(inp.x + 22, inp.cy - 19, 38, 38), icon="chat", color=pal.text_dim))
    nodes.append(T("ChatPlaceholder", Rect(inp.x + 72, inp.y, inp.w - 92, inp.h), "اكتب رسالة…",
                   "Type a message...", size=m.fs_body - 2, align="left", color=pal.text_dim))
    nodes.append(button(Rect(inner.right - 138, inner.bottom - 76, 138, 76), "SendButton", "إرسال", "Send",
                        pal, m, variant="primary", icon="arrow_right", size=m.fs_small + 2))
    return nodes


def build_store(brief: Brief, pal: Palette, m: M, canvas) -> list[Node]:
    w, h = canvas
    nodes = [N("backdrop", "Backdrop", Rect(0, 0, w, h), variant="glow", seed=113)]
    win = Rect(m.pad * 0.9, m.pad * 0.7, w - m.pad * 1.8, h - m.pad * 1.4)
    nodes += window(brief.title, brief.title, brief, pal, m, win, header_icon="gem")
    body = Rect(win.x + 24, win.y + m.header + 18, win.w - 48, win.h - m.header - m.footer - 20)
    nodes += tab_bar(Rect(body.x, body.y, body.w * 0.6, 58), ["جواهر", "باقات", "اشتراكات"],
                     ["Gems", "Bundles", "Subs"], pal, m, name="StoreTab")
    nodes += currency_pill(Rect(body.right - 200, body.y, 200, 58), "12,450", "coin", pal, m, "StoreCoins")
    cards = [("500 جوهرة", "500 gems", "gem", "4.99$", pal.info, ""),
             ("1,200 جوهرة", "1,200 gems", "gem", "9.99$", pal.accent, "الأكثر شراءً"),
             ("3,000 جوهرة", "3,000 gems", "gem", "19.99$", pal.accent2, "+10% هدية"),
             ("7,500 جوهرة", "7,500 gems", "crown", "44.99$", pal.warn, "أفضل قيمة")]
    cells = grid(Rect(body.x, body.y + 58 + m.gap, body.w, body.h - 58 - m.gap), 4, 1, gap=m.gap)
    for i, (c, (ar, en, ic, price, col, tag)) in enumerate(zip(cells, cards)):
        nodes.append(N("panel", f"Pack{i}", c, radius=m.radius, top=mix(pal.panel_hi, col, 0.2),
                       bottom=mix(pal.panel_lo, col, 0.08), stroke=mix(pal.stroke, col, 0.55),
                       stroke_w=pal.stroke_w + (1 if tag else 0), shadow=True))
        nodes.append(N("icon", f"Pack{i}Icon", Rect(c.cx - 46, c.y + 44, 92, 92), icon=ic, color=col,
                       secondary=mix(col, (0, 0, 0), 0.35)))
        if tag:
            nodes.append(N("badge", f"Pack{i}Tag", Rect(c.cx - 90, c.y + 14, 180, 36), color=col, radius=18))
            nodes.append(T(f"Pack{i}TagLabel", Rect(c.cx - 90, c.y + 14, 180, 36), tag, tag,
                           size=m.fs_small - 3, align="center", color=(255, 255, 255)))
        nodes.append(T(f"Pack{i}Name", Rect(c.x + 12, c.y + 150, c.w - 24, 44), ar, en, size=m.fs_head - 6,
                       align="center", color=pal.text))
        nodes.append(T(f"Pack{i}Desc", Rect(c.x + 16, c.y + 196, c.w - 32, 60),
                       "جواهر فورية + صندوق هدية", "Instant gems + bonus crate", size=m.fs_small,
                       align="center", color=pal.text_dim))
        nodes.append(button(Rect(c.x + 24, c.bottom - 92, c.w - 48, 64), f"Pack{i}Buy", price, price,
                            pal, m, variant="primary" if tag else "secondary", icon="cart"))
    nodes.append(T("StoreFooter", Rect(body.x, body.bottom - 40, body.w, 34),
                   "جميع المشتريات آمنة عبر Roblox", "All purchases are processed safely by Roblox",
                   size=m.fs_small, align="center", color=pal.text_dim))
    return nodes


BUILDERS = {
    "main_menu": build_main_menu,
    "shop": build_shop,
    "inventory": build_inventory,
    "settings": build_settings,
    "loading": build_loading,
    "leaderboard": build_leaderboard,
    "profile": build_profile,
    "hud": build_hud,
    "pause": build_pause,
    "login": build_login,
    "crate": build_crate,
    "quests": build_quests,
    "dialog": build_dialog,
    "wheel": build_wheel,
    "chat": build_chat,
    "store": build_store,
}


def build(brief: Brief, pal: Palette, canvas: tuple[int, int] = (1920, 1080)) -> DesignSpec:
    m = metrics(brief, pal)
    builder = BUILDERS.get(brief.kind, build_main_menu)
    nodes = builder(brief, pal, m, canvas)
    root = Node("root", "ScreenGui", Rect(0, 0, canvas[0], canvas[1]),
                props={"title": brief.title, "kind": brief.kind})
    root.children = nodes
    spec = DesignSpec(
        slug=slugify(brief.title, brief.kind), title=brief.title,
        subtitle=brief.subtitle or f"{brief.screen['en']} • {pal.name}",
        lang=brief.lang, canvas=canvas, palette=pal, brief=brief, root=root,
    )
    if brief.lang == "ar":
        mirror(root, canvas[0])
        for n in root.walk():
            if n.kind == "text":
                n.props["rtl_text"] = True
    else:
        for n in root.walk():
            le = n.props.get("label_en")
            if le:
                n.props["label"] = le
    spec.notes = _notes(brief, pal, m)
    return spec


def _notes(brief: Brief, pal: Palette, m: M) -> list[str]:
    ar = brief.lang == "ar"
    return [
        ("تم توليد التصميم بالكامل من وصف نصي واحد." if ar else "Whole design generated from one text prompt."),
        (f"النمط: {pal.name_ar} — نصف قطر الحواف {m.radius} بكسل." if ar
         else f"Style: {pal.name}, corner radius {m.radius}px."),
        ("كل زر يُصدَّر بأربع حالات: عادي/تحويم/ضغط/معطّل." if ar
         else "Every button is exported in four states: idle/hover/pressed/disabled."),
        ("الأصول قابلة للقص (9-slice) لذلك تتوسع دون فقدان الجودة." if ar
         else "Assets are 9-sliceable, so they scale without quality loss."),
        ("النصوص تُصدَّر كـ TextLabel حقيقية — يمكنك تغييرها أو ترجمتها داخل Studio." if ar
         else "Text is exported as real TextLabels - editable and localisable in Studio."),
    ]
