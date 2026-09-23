"""Roblox UI Forge — turn one sentence into a complete Roblox UI kit.

Public API::

    from forge import pipeline
    result = pipeline.run("متجر نيون احترافي مع تبويبات وزر شراء")
    print(result.zip_path)
"""
from . import brief, layouts, painter, pipeline, spec, themes
from .config import SETTINGS, Settings
from .pipeline import Result, run

__version__ = "1.0.0"
__all__ = ["brief", "layouts", "painter", "pipeline", "spec", "themes",
           "SETTINGS", "Settings", "Result", "run", "__version__"]
