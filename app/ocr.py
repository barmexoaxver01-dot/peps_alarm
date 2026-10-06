"""Best-effort OCR for printed expiration dates.

Tries a handful of common date formats found on packaging. Always
returns a suggestion only -- the human in receiving confirms or fixes
it before anything is saved. Never raises past this module; if
Tesseract isn't installed on the machine we just say so.
"""
import re
from datetime import datetime
from io import BytesIO

DATE_PATTERNS = [
    (r"(\d{2})[/\-.](\d{2})[/\-.](\d{4})", "%d/%m/%Y"),
    (r"(\d{2})[/\-.](\d{2})[/\-.](\d{2})\b", "%d/%m/%y"),
    (r"(\d{4})[/\-.](\d{2})[/\-.](\d{2})", "%Y/%m/%d"),
]


def extract_date_from_image(image_bytes: bytes) -> dict:
    """Returns {"ok": bool, "fecha": "YYYY-MM-DD" | None, "mensaje": str}."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {"ok": False, "fecha": None, "mensaje": "OCR no disponible: faltan pytesseract/Pillow."}

    try:
        image = Image.open(BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
    except Exception as exc:  # Tesseract binary missing, bad image, etc.
        return {"ok": False, "fecha": None, "mensaje": f"No se pudo leer la imagen: {exc}"}

    for pattern, fmt in DATE_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        raw = match.group(0).replace("-", "/").replace(".", "/")
        try:
            parsed = datetime.strptime(raw, fmt.replace("-", "/").replace(".", "/"))
            return {
                "ok": True,
                "fecha": parsed.strftime("%Y-%m-%d"),
                "mensaje": "Fecha detectada, por favor confirma que sea correcta.",
            }
        except ValueError:
            continue

    return {"ok": False, "fecha": None, "mensaje": "No se detectó una fecha legible. Captúrala manualmente."}
