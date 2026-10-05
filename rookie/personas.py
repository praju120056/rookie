"""Personas and the filters that change what the AI can actually see and do."""
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from PIL import Image, ImageFilter

LATIN = re.compile(r"[A-Za-z]")
DEVANAGARI = re.compile(r"[ऀ-ॿ]+(?:[\sऀ-ॿ]*[ऀ-ॿ])?")


@dataclass
class Persona:
    key: str
    name: str
    age: int
    about: str
    color: str = "teal"
    actions: list = field(default_factory=lambda: ["tap", "type", "back", "scroll", "wait", "done", "give_up"])
    patience: int = 4                # actions in a row that change nothing before giving up
    blur: float = 0                  # Gaussian blur radius applied to the screenshot
    min_font_px: float = 0           # text smaller than this is unreadable
    hide_icon_only: bool = False     # icon-only buttons aren't recognised as buttons
    reads_only_hindi: bool = False   # Latin-script text is unreadable
    slow_network: bool = False

    @property
    def label(self):
        return f"{self.name}, {self.age}"


def load(key, folder="personas"):
    data = yaml.safe_load(Path(folder, f"{key}.yaml").read_text(encoding="utf-8"))
    return Persona(key=key, **data)


def available(folder="personas"):
    return sorted(p.stem for p in Path(folder).glob("*.yaml"))


def _readable_text(p: Persona, text: str) -> str:
    if not p.reads_only_hindi or not LATIN.search(text):
        return text
    # Keep only the Hindi parts, digits and ₹; everything else is unreadable to this persona.
    keep = " ".join(DEVANAGARI.findall(text))
    keep += " " + " ".join(re.findall(r"₹\s?\d+|\b\d+\b", text))
    keep = keep.strip()
    return keep if keep else "[text in a language I can't read]"


def filter_elements(p: Persona, elements):
    """Return the numbered element list exactly as this persona perceives it."""
    seen = []
    for e in elements:
        if p.hide_icon_only and e["icon_only"]:
            continue  # she doesn't recognise a small unlabeled icon as something to tap
        text = e["text"] or e["aria"]
        if p.min_font_px and e["font_px"] < p.min_font_px:
            text = "[too small to read]"
        else:
            text = _readable_text(p, text) if text else ("[unlabeled icon]" if e["icon_only"] else "")
        seen.append({**e, "text": text})
    return seen


def filter_image(p: Persona, img: Image.Image) -> Image.Image:
    if p.blur:
        w, h = img.size
        img = img.resize((w // 2, h // 2)).filter(ImageFilter.GaussianBlur(p.blur)).resize((w, h))
    return img
