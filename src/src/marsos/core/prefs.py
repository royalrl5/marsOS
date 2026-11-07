"""User preferences (JSON in ~/.config/marsos/prefs.json)."""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path

from marsos import paths
from marsos.core import hardware


@dataclass
class Prefs:
    appearance: str = "auto"        # auto | light | dark
    accent: str = "blue"
    effects: str = "auto"           # auto | full | balanced | light
    text_scale: float = 1.0
    reduce_motion: bool = False
    command_as_ctrl: bool = False   # keyd: Command key acts like Ctrl (macOS shortcuts)
    natural_scroll: bool = True
    tap_to_click: bool = True
    show_advanced_apps: bool = False
    dock_size: int = 56
    family_contact: str = ""

    @staticmethod
    def file() -> Path:
        return paths.config_dir() / "prefs.json"

    @classmethod
    def load(cls) -> "Prefs":
        try:
            raw = json.loads(cls.file().read_text())
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self) -> None:
        f = self.file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(asdict(self), indent=2))

    def resolved_effects(self, hw: hardware.HardwareInfo | None = None) -> str:
        if self.effects != "auto":
            return self.effects
        return hardware.recommended_effects(hw or hardware.detect())

    @property
    def anim_factor(self) -> float:
        if self.reduce_motion:
            return 0.0
        return {"full": 1.0, "balanced": 0.8, "light": 0.5}.get(self.effects, 0.8)
