"""Generate the original Quantum Laboratory desktop icon from simple geometry."""
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    """Write PNG and multiresolution ICO files from the project's orbital mark."""
    target = Path(__file__).resolve().parents[1] / "desktop" / "assets"
    target.mkdir(parents=True, exist_ok=True)
    size = 512
    image = Image.new("RGBA", (size, size), (11, 16, 24, 255))
    draw = ImageDraw.Draw(image)
    cyan = (98, 216, 232, 255)
    purple = (169, 155, 248, 255)
    pale = (230, 237, 245, 255)
    draw.rounded_rectangle((18, 18, 494, 494), radius=110, fill=(18, 26, 38, 255),
                           outline=(48, 91, 108, 255), width=8)
    for box, color in [((90, 180, 422, 332), cyan), ((174, 78, 338, 434), purple)]:
        draw.ellipse(box, outline=color, width=13)
    draw.ellipse((204, 204, 308, 308), fill=pale)
    draw.ellipse((384, 214, 430, 260), fill=cyan)
    draw.ellipse((218, 58, 258, 98), fill=purple)
    image.save(target / "icon.png")
    image.save(target / "icon.ico", format="ICO", sizes=[(16, 16), (24, 24), (32, 32),
                                                           (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
