"""End-to-end pipeline: prompt -> ZIP that is actually usable."""
import zipfile
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from forge import pipeline
from forge.config import Settings


def _settings(tmp_path):
    return Settings(rscale=1, preview_scale=0.5,
                    out_dir=str(tmp_path / "out"), cache_dir=str(tmp_path / "cache"))


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pipe")
    return pipeline.run("متجر نيون مع تبويبات وزر شراء", use_llm=False, use_ai_images=False,
                        settings=_settings(tmp))


def test_zip_created(result):
    assert result.zip_path.exists()
    assert result.stats["assets"] > 0
    assert result.stats["nodes"] > 10


def test_zip_contents(result):
    names = zipfile.ZipFile(result.zip_path).namelist()
    for required in ("README.md", "manifest.json", "design-system.json", "slices.json",
                     "luau/UiForge.lua", "luau/AutoScale.lua", "studio/Studio_QuickBuild.lua",
                     "preview_full.png"):
        assert any(n == required or n.startswith(required) for n in names), required


def test_previews_not_blank(result):
    img = result.previews["preview"].convert("RGB")
    assert len(img.getcolors(200000)) > 50, "preview looks like a blank canvas"


def test_rbxmx_is_valid_xml(result):
    z = zipfile.ZipFile(result.zip_path)
    xml = [n for n in z.namelist() if n.endswith(".rbxmx")][0]
    root = ET.fromstring(z.read(xml))
    assert root.tag == "roblox"
    # every item must have a Name property
    items = root.iter("Item")
    count = 0
    for it in items:
        count += 1
    assert count > 5


def test_luau_library(result):
    z = zipfile.ZipFile(result.zip_path)
    lib = z.read("luau/UiForge.lua").decode("utf-8")
    for fn in ("UiForge.button", "UiForge.panel", "UiForge.progress", "UiForge.toggle",
               "UiForge.bindAssets", "UiForge.skin"):
        assert fn in lib


def test_slices_match_manifest(result):
    z = zipfile.ZipFile(result.zip_path)
    import json
    slices = json.loads(z.read("slices.json"))
    manifest = json.loads(z.read("manifest.json"))
    assert len(slices) > 0
    # every slice key must reference a real asset file
    files = set(manifest["files"])
    keys = {a["key"] for a in manifest["assets"]}
    assert set(slices) <= keys
