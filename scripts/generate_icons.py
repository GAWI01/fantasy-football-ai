"""Generate every app icon (web, iPhone home screen, PWA) from one source image.

Usage, from the repository root:

    python scripts/generate_icons.py                      # uses frontend/brand/app-icon-source.png
    python scripts/generate_icons.py path/to/new-icon.png # replaces the source, then regenerates

Needs Pillow (`python -m pip install pillow`).

The logo is designed in `frontend/brand/app-icon.svg`: a full-bleed square
whose artwork stays inside the central 80%. Export it to a 1024x1024 PNG
(any vector tool, or open the SVG in a browser and save a screenshot) as
`frontend/brand/app-icon-source.png`, then run this script.

Two crops of the source can be used:

* FULL: used where the icon is shown at 64 px or more (iPhone home screen,
  PWA, Android).
* MARK: used at 16-48 px (browser tab, favicon, the header logo).

The simple FF monogram reads at every size, so both are the whole image.
For a detailed illustration, set MARK_BOX to a tight crop of its main
subject. Boxes are fractions of the source (left, top, right, bottom).
Check the contact sheet written to frontend/brand/icon-preview.png.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SOURCE = FRONTEND / "brand" / "app-icon-source.png"

# Crop boxes as fractions of the source size, so a re-exported source at a
# different resolution keeps the same framing.
FULL_BOX = (0.0, 0.0, 1.0, 1.0)
MARK_BOX = (0.0, 0.0, 1.0, 1.0)
# True when the source keeps its artwork inside the central 80% (the
# Android maskable safe zone): the full-bleed image is then maskable as is.
# Otherwise it is shrunk onto MASKABLE_BACKGROUND.
SOURCE_IS_MASKABLE = True
MASKABLE_BACKGROUND = (8, 6, 22)
# Corner radius as a share of the side, close to the iOS/Android squircle.
CORNER = 0.2237


def _crop(source: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    width, height = source.size
    left, top, right, bottom = (round(value * size) for value, size in zip(box, (width, height, width, height)))
    side = min(right - left, bottom - top)
    return source.crop((left, top, left + side, top + side))


def _resize(image: Image.Image, size: int) -> Image.Image:
    return image.resize((size, size), Image.LANCZOS)


def _rounded(image: Image.Image, radius_share: float = CORNER) -> Image.Image:
    """Transparent corners, for places that show the image as-is."""
    size = image.size[0]
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), round(size * 4 * radius_share), fill=255)
    out = image.convert("RGBA")
    out.putalpha(mask.resize((size, size), Image.LANCZOS))
    return out


def _maskable(full: Image.Image, size: int) -> Image.Image:
    """Android adaptive icon: the artwork inside the central 80% safe zone."""
    if SOURCE_IS_MASKABLE:
        return _resize(full, size)
    canvas = Image.new("RGB", (size, size), MASKABLE_BACKGROUND)
    inner = round(size * 0.8)
    offset = (size - inner) // 2
    canvas.paste(_rounded(_resize(full, inner), 0.18), (offset, offset), _rounded(_resize(full, inner), 0.18))
    return canvas


def generate(source_path: Path = SOURCE) -> list[Path]:
    source = Image.open(source_path).convert("RGB")
    full, mark = _crop(source, FULL_BOX), _crop(source, MARK_BOX)
    app, public, brand = FRONTEND / "app", FRONTEND / "public" / "icons", FRONTEND / "brand"
    public.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save(image: Image.Image, path: Path, **options) -> None:
        if path.suffix == ".png":
            options.setdefault("optimize", True)
        image.save(path, **options)
        written.append(path)

    # Browser tab: favicon.ico (16/32/48) and a 32 px PNG, both from the mark.
    save(_rounded(_resize(mark, 48), 0.22), app / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    save(_rounded(_resize(mark, 32), 0.22), app / "icon.png")
    # iPhone home screen: opaque and full-bleed; iOS rounds the corners itself.
    save(_resize(full, 180), app / "apple-icon.png")
    # PWA / Android.
    save(_rounded(_resize(full, 192)), public / "icon-192.png")
    save(_rounded(_resize(full, 512)), public / "icon-512.png")
    save(_maskable(full, 512), public / "icon-maskable-512.png")
    # Logo in the app header (shown at 34 px; 128 px stays sharp on 3x screens).
    save(_rounded(_resize(mark, 128), 0.24), public / "logo-mark.png")

    # A contact sheet to eyeball the crops at every size.
    sheet = Image.new("RGB", (760, 250), (24, 24, 32))
    x = 12
    for size in (180, 96, 64):
        tile = _rounded(_resize(full, size))
        sheet.paste(tile, (x, 12), tile)
        x += size + 24
    x = 12
    for size in (48, 32, 16):
        tile = _rounded(_resize(mark, size), 0.22)
        sheet.paste(tile, (x, 205), tile)
        x += size + 24
    save(sheet, brand / "icon-preview.png")
    return written


if __name__ == "__main__":
    if len(sys.argv) > 1:
        new_source = Path(sys.argv[1]).resolve()
        if new_source != SOURCE.resolve():
            shutil.copyfile(new_source, SOURCE)
    for path in generate():
        print(path.relative_to(ROOT))
