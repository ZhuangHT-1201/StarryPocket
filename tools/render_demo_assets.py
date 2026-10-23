"""Render the original Nova demo artwork into the PNG assets used by the app."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "source" / "nova-template.svg"
SOURCE_OUTPUT = ROOT / "assets" / "source" / "nova.svg"
ASSETS = ROOT / "assets"

VARIANTS = {
    "aurora": {
        "SCARF": "#63bff2",
        "SCARF_DEEP": "#4487d8",
        "COAT": "#dff6ff",
        "COAT_DEEP": "#bce7fb",
        "ACCENT": "#ffd86f",
    },
    "ember": {
        "SCARF": "#ff917c",
        "SCARF_DEEP": "#da6374",
        "COAT": "#fff0dc",
        "COAT_DEEP": "#ffd6b7",
        "ACCENT": "#ff9c76",
    },
    "mint": {
        "SCARF": "#70d5b6",
        "SCARF_DEEP": "#3da58d",
        "COAT": "#e9fff7",
        "COAT_DEEP": "#c6f3e4",
        "ACCENT": "#75d8c2",
    },
}


def render_variant(name: str, colors: dict[str, str]) -> Path:
    svg = TEMPLATE.read_text(encoding="utf-8")
    for key, value in colors.items():
        svg = svg.replace(f"__{key}__", value)

    renderer = QSvgRenderer(svg.encode("utf-8"))
    image = QImage(768, 1080, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, image.width(), image.height()))
    painter.end()

    target = ASSETS / f"nova_{name}.png"
    image.save(str(target))
    return target


def make_icon(character_path: Path) -> Path:
    character = Image.open(character_path).convert("RGBA")
    head = character.crop((105, 80, 660, 635))
    size = 512
    head.thumbnail((490, 490), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    background = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = background.load()
    for y in range(size):
        mix = y / max(1, size - 1)
        color = (
            round(226 + (255 - 226) * mix),
            round(246 + (230 - 246) * mix),
            round(255 + (216 - 255) * mix),
            255,
        )
        for x in range(size):
            pixels[x, y] = color
    shape = ImageDraw.Draw(background)
    shape.ellipse((-70, 250, 330, 650), fill=(127, 205, 255, 120))
    shape.ellipse((300, -80, 660, 280), fill=(255, 217, 111, 135))
    circle_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(circle_mask).ellipse((10, 10, size - 10, size - 10), fill=255)
    background.putalpha(circle_mask)
    canvas.alpha_composite(background)

    avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    avatar.alpha_composite(head, ((size - head.width) // 2, (size - head.height) // 2))
    avatar.putalpha(ImageChops.multiply(avatar.getchannel("A"), circle_mask))
    canvas.alpha_composite(avatar)

    ring = ImageDraw.Draw(canvas)
    ring.ellipse((10, 10, size - 10, size - 10), outline=(255, 255, 255, 255), width=12)
    target = ASSETS / "icon.png"
    canvas.save(target)
    canvas.save(ASSETS / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return target


def main() -> int:
    _app = QGuiApplication(sys.argv)
    source = TEMPLATE.read_text(encoding="utf-8")
    for key, value in VARIANTS["aurora"].items():
        source = source.replace(f"__{key}__", value)
    SOURCE_OUTPUT.write_text(source, encoding="utf-8")
    rendered = []
    for variant_name, variant_colors in VARIANTS.items():
        rendered.append(render_variant(variant_name, variant_colors))
        print(rendered[-1])
    print(make_icon(rendered[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
