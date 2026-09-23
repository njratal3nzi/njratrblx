"""`.rbxmx` model export (secondary path).

Roblox model XML is strict about enum tokens, so this exporter deliberately
sticks to value types that are unambiguous (UDim2 / UDim / Color3 / Rect / number
/ bool / string) plus UICorner and UIStroke children.  Fonts and gradients are
left to the Luau builder, which is the recommended import path.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from ..spec import DesignSpec, Node
from ..themes import color3

HEADER = ('<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">\n')


def _prop_str(name: str, value: str) -> str:
    return f'<string name="{name}">{escape(value)}</string>'


def _prop_num(name: str, value: float) -> str:
    return f'<float name="{name}">{value:g}</float>'


def _prop_int(name: str, value: int) -> str:
    return f'<int name="{name}">{int(value)}</int>'


def _prop_bool(name: str, value: bool) -> str:
    return f'<bool name="{name}">{"true" if value else "false"}</bool>'


def _prop_udim2(name: str, sx: float, ox: int, sy: float, oy: int) -> str:
    return (f'<UDim2 name="{name}"><XS>{sx:.6g}</XS><XO>{int(ox)}</XO>'
            f'<YS>{sy:.6g}</YS><YO>{int(oy)}</YO></UDim2>')


def _prop_udim(name: str, s: float, o: int) -> str:
    return f'<UDim name="{name}"><S>{s:.6g}</S><O>{int(o)}</O></UDim>'


def _prop_color(name: str, rgb) -> str:
    r, g, b = color3(rgb)
    return f'<Color3 name="{name}"><R>{r:.6g}</R><G>{g:.6g}</G><B>{b:.6g}</B></Color3>'


def _prop_rect(name: str, rect) -> str:
    return (f'<Rect name="{name}"><XMin>{rect[0]:.6g}</XMin><YMin>{rect[1]:.6g}</YMin>'
            f'<XMax>{rect[2]:.6g}</XMax><YMax>{rect[3]:.6g}</YMax></Rect>')


def _item(cls: str, referent: str, props: str, children: str = "") -> str:
    return (f'<Item class="{cls}" referent="{referent}"><Properties>{props}</Properties>'
            f'{children}</Item>\n')


ALIGN = {"left": 0, "center": 1, "right": 2}
SCALE_TYPE_SLICE = 1


class _Counter:
    def __init__(self):
        self.n = 0

    def next(self) -> str:
        self.n += 1
        return f"RBX{self.n}"


def _emit(node: Node, spec: DesignSpec, ctr: _Counter) -> str:
    if node.kind == "root":
        return "".join(_emit(c, spec, ctr) for c in node.children)
    cw, ch = spec.canvas
    r, p = node.rect, node.props
    ref = ctr.next()
    props = [_prop_str("Name", node.name),
             _prop_udim2("Position", r.x / cw, 0, r.y / ch, 0),
             _prop_udim2("Size", max(0.0, r.w / cw), 0, max(0.0, r.h / ch), 0),
             _prop_int("ZIndex", node.props.get("z", 1))]
    children = ""
    asset = spec.asset_for(node.name)

    if node.kind == "text":
        c = p.get("color") or (255, 255, 255)
        props += [
            _prop_num("BackgroundTransparency", 1.0),
            _prop_str("Text", str(p.get("label", ""))),
            _prop_color("TextColor3", c),
            _prop_num("TextSize", float(int(p.get("font_size", 24)))),
            _prop_int("TextXAlignment", ALIGN.get(p.get("align", "left"), 0)),
            _prop_int("TextYAlignment", 1),
            _prop_bool("TextWrapped", True),
            _prop_bool("RichText", True),
            _prop_str("ClassName", "TextLabel"),
        ]
        cls = "TextLabel"
    elif node.kind == "scrim":
        props += [_prop_color("BackgroundColor3", (0, 0, 0)),
                  _prop_num("BackgroundTransparency", round(1 - float(p.get("alpha", 0.5)), 4)),
                  _prop_int("BorderSizePixel", 0)]
        cls = "Frame"
    elif node.kind == "divider":
        props += [_prop_color("BackgroundColor3", p.get("color") or spec.palette.stroke),
                  _prop_num("BackgroundTransparency", 0.25),
                  _prop_int("BorderSizePixel", 0)]
        cls = "Frame"
    elif node.kind == "button":
        c = p.get("color") or (255, 255, 255)
        props += [
            _prop_str("Text", str(p.get("label", ""))),
            _prop_color("TextColor3", c),
            _prop_num("TextSize", float(int(p.get("font_size", 26)))),
            _prop_int("TextXAlignment", ALIGN.get(p.get("align", "center"), 1)),
            _prop_bool("AutoButtonColor", True),
            _prop_int("BorderSizePixel", 0),
        ]
        cls = "TextButton"
    else:
        cls = "ImageLabel" if node.kind in ("avatar", "icon", "wheel", "minimap", "backdrop") else "Frame"
        props += [_prop_int("BorderSizePixel", 0)]
        if cls == "ImageLabel":
            props += [_prop_str("Image", ""), _prop_num("ImageTransparency", 0.0),
                      _prop_num("BackgroundTransparency", 1.0)]
        else:
            props += [_prop_color("BackgroundColor3", p.get("top") or p.get("color") or spec.palette.panel),
                      _prop_num("BackgroundTransparency", 0.0)]

    # remove the accidental ClassName string prop used for text nodes
    props = [q for q in props if 'name="ClassName"' not in q]

    radius = p.get("radius")
    if radius is not None:
        children += _item("UICorner", ctr.next(), _prop_udim("CornerRadius", 0, float(radius)))
    stroke = p.get("stroke")
    if stroke and p.get("stroke_w", 0):
        children += _item("UIStroke", ctr.next(),
                          _prop_color("Color", stroke) + _prop_num("Thickness", float(p["stroke_w"])) +
                          _prop_int("ApplyStrokeMode", 0))
    if asset is not None and asset.slice and cls in ("ImageLabel", "Frame", "TextButton"):
        props += [_prop_int("ScaleType", SCALE_TYPE_SLICE), _prop_rect("SliceCenter", asset.slice)]
    return _item(cls, ref, "".join(props), children)


def build_rbxmx(spec: DesignSpec) -> str:
    ctr = _Counter()
    gui_ref = ctr.next()
    gui_props = [_prop_str("Name", spec.slug.title()),
                 _prop_bool("Enabled", True),
                 _prop_bool("ResetOnSpawn", False),
                 _prop_int("ZIndexBehavior", 1),
                 _prop_bool("IgnoreGuiInset", True)]
    body = "".join(_emit(c, spec, ctr) for c in spec.root.children)
    return HEADER + _item("ScreenGui", gui_ref, "".join(gui_props), body) + "</roblox>\n"
