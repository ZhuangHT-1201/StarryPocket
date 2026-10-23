"""Create privacy-safe demo screenshots from the real StarryPocket window."""

from __future__ import annotations

import math
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
FONT_REGULAR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf"
FONT_BOLD = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeuib.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def capture_window(pose: str, message: str, target: Path, temp_root: Path) -> Image.Image:
    env = os.environ.copy()
    env["APPDATA"] = str(temp_root)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "main.py"),
            "--preview",
            f"--pose={pose}",
            f"--speech={message}",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    raw = ROOT / "_preview.png"
    image = Image.open(raw).convert("RGBA")
    image.save(target)
    raw.unlink(missing_ok=True)
    return image


def make_background(width: int, height: int, seed: int = 23) -> Image.Image:
    rng = random.Random(seed)
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        mix = y / max(1, height - 1)
        top = (10, 19, 44)
        bottom = (49, 35, 73)
        color = tuple(round(a + (b - a) * mix) for a, b in zip(top, bottom))
        for x in range(width):
            vignette = 1 - (
                ((x / width - 0.5) ** 2 + (y / height - 0.48) ** 2) * 0.22
            )
            pixels[x, y] = tuple(round(c * vignette) for c in color)

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.ellipse((-180, -180, 660, 520), fill=(58, 167, 230, 92))
    draw.ellipse((720, -240, 1560, 540), fill=(255, 146, 187, 72))
    draw.ellipse((640, 460, 1500, 1100), fill=(127, 97, 224, 72))
    image = Image.alpha_composite(image.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(95)))

    stars = Image.new("RGBA", image.size, (0, 0, 0, 0))
    star_draw = ImageDraw.Draw(stars)
    for _ in range(150):
        x = rng.randrange(width)
        y = rng.randrange(int(height * 0.72))
        radius = rng.choice((1, 1, 1, 2, 2, 3))
        alpha = rng.randrange(70, 210)
        star_draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(255, 246, 212, alpha),
        )
    image = Image.alpha_composite(image, stars)

    mountains = Image.new("RGBA", image.size, (0, 0, 0, 0))
    mountain_draw = ImageDraw.Draw(mountains)
    mountain_draw.polygon(
        [
            (0, 710),
            (150, 565),
            (290, 672),
            (430, 520),
            (620, 697),
            (810, 548),
            (1000, 680),
            (1170, 535),
            (1440, 700),
            (1440, 900),
            (0, 900),
        ],
        fill=(24, 31, 65, 220),
    )
    mountain_draw.polygon(
        [
            (0, 785),
            (230, 665),
            (480, 780),
            (740, 625),
            (990, 775),
            (1230, 660),
            (1440, 760),
            (1440, 900),
            (0, 900),
        ],
        fill=(17, 23, 50, 235),
    )
    image = Image.alpha_composite(image, mountains)

    taskbar = Image.new("RGBA", (width, 56), (15, 18, 36, 215))
    taskbar_draw = ImageDraw.Draw(taskbar)
    for index in range(5):
        x = 24 + index * 52
        taskbar_draw.rounded_rectangle(
            (x, 12, x + 34, 44), radius=8, fill=(255, 255, 255, 48 + index * 6)
        )
    taskbar_draw.text((width - 132, 14), "09:41   Fri", font=font(17), fill=(255, 255, 255, 210))
    image.alpha_composite(taskbar, (0, height - 56))
    return image


def place_window(
    background: Image.Image,
    window: Image.Image,
    center_x: int,
    top: int,
    display_size: tuple[int, int],
) -> None:
    pet = window.resize(display_size, Image.Resampling.LANCZOS)
    x = center_x - display_size[0] // 2
    shadow = Image.new("RGBA", background.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        (
            x + display_size[0] * 0.2,
            top + display_size[1] - 36,
            x + display_size[0] * 0.8,
            top + display_size[1] + 4,
        ),
        fill=(4, 8, 20, 120),
    )
    background.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(15)))
    background.alpha_composite(pet, (x, top))


def make_desktop(raw: Image.Image, target: Path) -> None:
    background = make_background(1440, 900)
    place_window(background, raw, 1170, 290, (360, 520))
    label = Image.new("RGBA", (470, 170), (16, 24, 52, 0))
    draw = ImageDraw.Draw(label)
    draw.text((4, 8), "STARRY POCKET", font=font(46, bold=True), fill=(255, 255, 255, 245))
    draw.text(
        (4, 67),
        "A tiny guardian for your desktop.",
        font=font(24),
        fill=(205, 222, 255, 230),
    )
    draw.rounded_rectangle((4, 115, 197, 154), radius=19, fill=(255, 255, 255, 35))
    draw.text((24, 122), "Drag  ·  Click  ·  Smile", font=font(17), fill=(255, 255, 255, 210))
    background.alpha_composite(label, (120, 210))
    background.convert("RGB").save(target, quality=95)


def make_outfits(raws: dict[str, Image.Image], target: Path) -> None:
    canvas = make_background(1440, 840, seed=41)
    shade = Image.new("RGBA", canvas.size, (9, 14, 31, 80))
    canvas.alpha_composite(shade)
    draw = ImageDraw.Draw(canvas)
    draw.text((72, 58), "Three moods. One tiny guardian.", font=font(42, bold=True), fill="white")
    draw.text(
        (74, 116),
        "Double-click Nova or choose an outfit from the context menu.",
        font=font(22),
        fill=(201, 215, 239, 235),
    )
    colors = {
        "aurora": ((79, 174, 235, 72), "#65c8ff"),
        "ember": ((244, 133, 117, 72), "#ff9b7c"),
        "mint": ((94, 201, 163, 72), "#73d9bb"),
    }
    labels = {"aurora": "Aurora", "ember": "Ember", "mint": "Mint"}
    centers = (270, 720, 1170)
    for center, key in zip(centers, ("aurora", "ember", "mint")):
        box = (center - 190, 180, center + 190, 785)
        draw.rounded_rectangle(box, radius=38, fill=colors[key][0], outline=(255, 255, 255, 72), width=2)
        place_window(canvas, raws[key], center, 194, (292, 422))
        pill_width = 130
        draw.rounded_rectangle(
            (center - pill_width // 2, 744, center + pill_width // 2, 790),
            radius=23,
            fill=(255, 255, 255, 220),
        )
        rect = draw.textbbox((0, 0), labels[key], font=font(22, bold=True))
        text_width = rect[2] - rect[0]
        draw.text(
            (center - text_width / 2, 754),
            labels[key],
            font=font(22, bold=True),
            fill=colors[key][1],
        )
    canvas.convert("RGB").save(target, quality=95)


def make_interactions(raws: list[tuple[str, Image.Image]], target: Path) -> None:
    canvas = make_background(1440, 820, seed=77)
    overlay = Image.new("RGBA", canvas.size, (8, 12, 28, 65))
    canvas.alpha_composite(overlay)
    draw = ImageDraw.Draw(canvas)
    draw.text((70, 50), "A pocketful of tiny interactions.", font=font(40, bold=True), fill="white")
    captions = ("A quiet hello", "A little encouragement", "A bedtime reminder")
    centers = (270, 720, 1170)
    for center, caption, (_key, raw) in zip(centers, captions, raws):
        draw.rounded_rectangle(
            (center - 190, 150, center + 190, 760),
            radius=36,
            fill=(22, 31, 61, 235),
            outline=(255, 255, 255, 62),
            width=2,
        )
        place_window(canvas, raw, center, 163, (296, 428))
        rect = draw.textbbox((0, 0), caption, font=font(20, bold=True))
        width = rect[2] - rect[0]
        draw.text(
            (center - width / 2, 716),
            caption,
            font=font(20, bold=True),
            fill=(237, 244, 255, 245),
        )
    canvas.convert("RGB").save(target, quality=95)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="starrypocket_") as temp:
        temp_root = Path(temp)
        raws = {}
        for pose in ("aurora", "ember", "mint"):
            raws[pose] = capture_window(
                pose,
                "A little starlight for your desktop.",
                temp_root / f"{pose}.png",
                temp_root,
            )
        interaction_one = capture_window(
            "aurora",
            "Need a tiny break? Nova is here.",
            temp_root / "interaction-one.png",
            temp_root,
        )
        interaction_two = capture_window(
            "ember",
            "Boo! Made you smile.",
            temp_root / "interaction-two.png",
            temp_root,
        )
        interaction_three = capture_window(
            "mint",
            "The moon says it is bedtime.",
            temp_root / "interaction-three.png",
            temp_root,
        )

        make_desktop(raws["aurora"], OUT / "desktop.png")
        make_outfits(raws, OUT / "outfits.png")
        make_interactions(
            [
                ("aurora", interaction_one),
                ("ember", interaction_two),
                ("mint", interaction_three),
            ],
            OUT / "interactions.png",
        )
        print(f"Saved README screenshots to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
