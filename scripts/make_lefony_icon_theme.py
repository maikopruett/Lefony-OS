#!/usr/bin/env python3
"""Generate Lefony's green icon set from the pinned light upstream artwork."""

from __future__ import annotations

import argparse
import colorsys
from pathlib import Path

from PIL import Image


REPO = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO / "build/lefony-prime-g2/themes/themes/local/epsilon_light"
DEFAULT_OUTPUT = (
    REPO / "ports/lefony-prime-g2/themes/themes/local/lefony_light"
)
SOURCE_YELLOW_BLUE = 52
SOURCE_YELLOW_CHROMA = 255 - SOURCE_YELLOW_BLUE
LEFONY_GREEN = (0x46, 0x66, 0x45)


def is_yellow_accent(red: int, green: int, blue: int) -> bool:
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    if maximum - minimum < 18:
        return False
    hue, saturation, _ = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    degrees = hue * 360
    return 24 <= degrees <= 58 and saturation >= 0.18 and red >= green > blue


def recolor(pixel: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    red, green, blue, alpha = pixel
    if alpha == 0 or not is_yellow_accent(red, green, blue):
        return pixel

    # Upstream's principal yellow is #FFB734. Treat anti-aliased pixels as a
    # mixture of that source color and a neutral background, then substitute
    # #466645 for the colored component. This keeps light and dark edge
    # coverage intact without leaving a yellow fringe.
    strength = min(1.0, max(0.0, (red - blue) / SOURCE_YELLOW_CHROMA))
    if strength >= 0.999:
        neutral = 0.0
    else:
        neutral = (blue - strength * SOURCE_YELLOW_BLUE) / (1.0 - strength)
        neutral = min(255.0, max(0.0, neutral))
    converted = tuple(
        round(strength * component + (1.0 - strength) * neutral)
        for component in LEFONY_GREEN
    )
    return converted + (alpha,)


def convert(source: Path, output: Path) -> tuple[int, int]:
    image = Image.open(source).convert("RGBA")
    pixels = image.load()
    changed = 0
    for y in range(image.height):
        for x in range(image.width):
            original = pixels[x, y]
            replacement = recolor(original)
            if replacement != original:
                pixels[x, y] = replacement
                changed += 1
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)
    return changed, image.width * image.height


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.source.is_dir():
        raise SystemExit(f"icon source directory is missing: {args.source}")

    files = sorted(args.source.rglob("*.png"))
    changed = 0
    pixels = 0
    for source in files:
        output = args.output / source.relative_to(args.source)
        file_changed, file_pixels = convert(source, output)
        changed += file_changed
        pixels += file_pixels
    print(f"{args.output}: {len(files)} icons, {changed}/{pixels} pixels recolored")


if __name__ == "__main__":
    main()
