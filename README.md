# PEPS ALARM

Control de mermas por caducidad en piso de venta. La persona de **recibo**
escanea el codigo de barras al dar entrada a un producto y captura su fecha
de caducidad; **piso de venta** ve un semaforo de alertas y marca los
productos que ya retiro; **admin** ajusta los umbrales de alerta y da de
alta usuarios.

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- (Opcional, solo para OCR) [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
  instalado y en el PATH. Sin el, la captura manual de fecha sigue
  funcionando normal -- el OCR es un atajo, no un requisito.

## Instalacion

```powershell
cd peps_alarm
uv venv
uv pip install -e . --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
.venv\Scripts\python.exe seed.py
```

El `seed.py` crea el primer usuario administrador:

- usuario: `admin`
- contraseña: `peps2024`

**Cambia esa contraseña en cuanto entres** (desde el panel de Admin puedes
crear tu propio usuario; borrar/editar usuarios existentes se puede agregar
despues si hace falta).

## Correr la app

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8899
```

Abre `http://127.0.0.1:8899/login`.

## Roles

| Rol     | Puede entrar a      | Que hace                                      |
|---------|---------------------|------------------------------------------------|
| recibo  | `/recibo`           | Escanea/teclea codigo, captura fecha, registra lote |
| piso    | `/dashboard`        | Ve alarmas semaforo, marca lotes como retirados |
| admin   | todo + `/admin`     | Ajusta umbrales de dias, crea usuarios          |

## Semaforo de alertas

Configurable desde `/admin` (valores por default: amarillo 15 dias, rojo 7
dias):

- **Verde**: falta mas de `dias_amarillo` para caducar
- **Amarillo**: faltan `dias_amarillo` dias o menos
- **Rojo**: faltan `dias_rojo` dias o menos
- **Caducado** (negro): la fecha ya paso

## OCR de fecha de caducidad (opcional)

En el formulario de recibo hay un campo para subir/tomar foto del empaque.
Si Tesseract esta instalado, intenta detectar una fecha en la imagen y la
persona de recibo puede usarla con un clic -- pero **siempre se puede
corregir o ignorar**, nunca se guarda sola. Si Tesseract no esta instalado,
el campo simplemente avisa que no esta disponible, sin romper el resto de
la app.

## Uso en celular (PWA)

La app es responsive y se puede "instalar" en el telefono como si fuera una
app nativa, sin pasar por App Store ni Play Store:

- **Android (Chrome)**: menu (tres puntos) -> "Instalar app" o "Agregar a
  pantalla de inicio"
- **iPhone (Safari)**: boton de compartir -> "Agregar a pantalla de inicio"

Una vez instalada, abre en pantalla completa con su propio icono, igual que
cualquier app. Internamente sigue siendo la misma app web -- incluido el
servidor FastAPI -- no hay nada nativo que compilar ni publicar.

**Importante**: el acceso a la camara (para escanear codigo de barras) solo
funciona en `localhost` o en sitios servidos por **HTTPS**. Para probarlo
desde un celular real conectado a tu misma red, vas a necesitar exponer la
app por HTTPS (por ejemplo detras de un proxy con certificado, o desplegada
en un servidor con TLS). En `localhost` durante desarrollo funciona sin
problema.

### Escaneo con camara (recibo)

En el formulario de recibo hay un boton "Camara" junto al campo de codigo
de barras. Abre la camara del telefono, lee codigos de barras comunes
(EAN-13, UPC-A, Code128, etc. via la libreria `html5-qrcode`) y llena el
campo automaticamente -- el lector USB de escritorio sigue funcionando
igual de bien si prefieres seguir usando eso en el area fija de recibo.


