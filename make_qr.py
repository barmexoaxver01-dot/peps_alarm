"""One-off: genera un QR con la URL de PEPS ALARM en la red local.
No es parte del app en ejecucion, solo una utileria de instalacion.
"""
import sys

import qrcode

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/login"

img = qrcode.make(url)
img.save("peps_alarm_qr.png")
print(f"QR generado para: {url}")
print("Guardado en peps_alarm_qr.png")
