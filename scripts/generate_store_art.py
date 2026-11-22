"""Generate the auto-fill icon and small promo tile from code-native shapes.

Run with Pillow installed: python3 scripts/generate_store_art.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "apps/extension/public/icons"
STORE = ROOT / "release/store"
BLUE = (49, 95, 232)
NAVY = (24, 49, 111)
WHITE = (255, 255, 255)
GREEN = (91, 222, 170)


def icon(size: int) -> Image.Image:
    scale = 4
    image = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    def box(values: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        return tuple(round(value * size * scale / 128) for value in values)
    draw.rounded_rectangle(box((16, 16, 112, 112)), radius=round(22 * size * scale / 128), fill=BLUE)
    draw.rounded_rectangle(box((42, 31, 86, 96)), radius=round(6 * size * scale / 128), fill=WHITE)
    for y, width in ((47, 24), (58, 24), (69, 15)):
        draw.rounded_rectangle(box((51, y, 51 + width, y + 4)), radius=round(2 * size * scale / 128), fill=(174, 193, 247))
    draw.ellipse(box((67, 65, 101, 99)), fill=GREEN)
    draw.line([box((75, 82, 75, 82))[:2], box((81, 88, 81, 88))[:2], box((93, 74, 93, 74))[:2]],
              fill=NAVY, width=max(1, round(5 * size * scale / 128)), joint="curve")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Arial Bold.ttf" if bold else "Arial.ttf"
    candidates = [Path("/System/Library/Fonts/Supplemental") / name,
                  Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    raise RuntimeError("Install Arial or DejaVu Sans to generate the store artwork")


def promo() -> Image.Image:
    image = Image.new("RGB", (440, 280), NAVY)
    draw = ImageDraw.Draw(image)
    for y in range(280):
        blend = y / 279
        draw.line((0, y, 440, y), fill=(round(24 + 18 * blend), round(49 + 26 * blend), round(111 + 52 * blend)))
    draw.ellipse((250, -108, 550, 192), outline=(75, 122, 246), width=2)
    draw.ellipse((276, -82, 524, 166), outline=(75, 122, 246), width=2)
    draw.rounded_rectangle((269, 77, 407, 215), radius=30, fill=(35, 67, 150))
    image.paste(icon(132), (272, 80), icon(132))
    draw.text((31, 72), "auto-fill", font=font(42, True), fill=WHITE)
    draw.text((33, 132), "Review before you fill.", font=font(19), fill=(218, 228, 255))
    draw.text((33, 161), "Submit applications yourself.", font=font(16), fill=(218, 228, 255))
    draw.rounded_rectangle((33, 219, 173, 248), radius=14, fill=GREEN)
    draw.text((50, 225), "User controlled", font=font(13, True), fill=NAVY)
    return image


def main() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    STORE.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 48, 128):
        icon(size).save(ICONS / f"icon-{size}.png")
    promo().save(STORE / "promo-small-440x280.png")


if __name__ == "__main__":
    main()
