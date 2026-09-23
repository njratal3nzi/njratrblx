"""Brief parser behaviour."""
from forge.brief import parse, detect_lang


def test_kind_detection_arabic():
    b = parse("ابغى واجهة متجر احترافية بستايل نيون")
    assert b.kind == "shop"


def test_kind_detection_english():
    b = parse("I need an inventory grid with tabs")
    assert b.kind == "inventory"


def test_style_detection():
    assert parse("store with gold luxury style").style == "royal"
    assert parse("واجهة خضراء سامة").style == "toxic"


def test_language_detection():
    assert detect_lang("متجر") == "ar"
    assert detect_lang("shop menu") == "en"


def test_features_default_for_kind():
    b = parse("متجر")
    assert b.has("tabs", "grid", "currency")


def test_title_from_quotes():
    b = parse('شاشة بعنوان "سوق الأبطال"')
    assert "الأبطال" in b.title
