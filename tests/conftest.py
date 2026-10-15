"""Корень проекта в sys.path, чтобы работали и `pytest tests -q`, и `python -m pytest tests -q`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
