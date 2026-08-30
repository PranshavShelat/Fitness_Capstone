import os

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets", "anatomy")
RED = (214, 39, 40)


def render_fault_diagram(image_filename, region, label):
    """image_filename: e.g. 'knee.png' in assets/anatomy/ - a public-domain
    anatomical reference plate (Gray's Anatomy, 1918).
    region: (x0, y0, x1, y1) as fractions (0-1) of that image's width/height -
    the area to circle in red for this specific fault.
    label: short text drawn above the highlighted region.
    Returns a PIL.Image.Image - fpdf2's image() accepts this directly.
    """
    img = Image.open(os.path.join(ASSETS_DIR, image_filename)).convert("RGB").copy()
    draw = ImageDraw.Draw(img)

    width, height = img.size
    x0, y0, x1, y1 = region
    box = (x0 * width, y0 * height, x1 * width, y1 * height)

    outline_width = max(3, width // 100)
    draw.ellipse(box, outline=RED, width=outline_width)

    font = ImageFont.load_default(size=max(16, width // 20))
    text_bbox = draw.textbbox((0, 0), label, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    text_x = (box[0] + box[2]) / 2 - text_w / 2
    text_y = max(box[1] - text_h - 10, 4)

    # small white backing so the label stays legible over the illustration
    draw.rectangle(
        [text_x - 4, text_y - 2, text_x + text_w + 4, text_y + text_h + 4],
        fill=(255, 255, 255),
    )
    draw.text((text_x, text_y), label, fill=RED, font=font)

    return img
