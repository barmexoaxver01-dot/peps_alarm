"""One-off script to generate placeholder PWA icons. Not part of the app."""
from PIL import Image, ImageDraw, ImageFont

for size in (192, 512):
    img = Image.new("RGB", (size, size), "#111827")
    draw = ImageDraw.Draw(img)
    pad = size // 10
    draw.rectangle([pad, pad, size - pad, size - pad], outline="#facc15", width=max(4, size // 40))
    try:
        font = ImageFont.truetype("arial.ttf", size // 6)
    except Exception:
        font = ImageFont.load_default()
    text = "PEPS"
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2, (size - h) / 2 - bbox[1]), text, fill="#facc15", font=font)
    img.save(f"app/static/icon-{size}.png")

print("iconos listos")
