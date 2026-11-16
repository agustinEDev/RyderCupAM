"""
Las páginas de /docs (Swagger UI) y /redoc (ReDoc), con sus recursos fijados e íntegros.

P-02 (auditoría del 16 nov 2026): `get_swagger_ui_html` y `get_redoc_html` de FastAPI
cargan `swagger-ui-dist@5` y `redoc@2` de jsDelivr, con versión flotante y sin SRI (no
admiten `integrity`), y las páginas iban sin CSP. Una versión maliciosa de cualquiera de
los dos, o un jsDelivr comprometido, se habría ejecutado en el origen de la API con la
sesión del administrador. Aquí el HTML es propio:

- cada fichero del CDN con versión exacta, `integrity` (sha384) y `crossorigin`;
- el script de arranque de Swagger es fijo (la URL del esquema va en un atributo
  `data-`), así que su hash sha256 entra en la CSP y no hace falta `'unsafe-inline'`;
- `CSP_DE_LA_DOCUMENTACION`, la CSP de las dos páginas: solo esos ficheros concretos
  pueden ejecutarse.

Para subir de versión: cambiar la versión y su hash, sacado del propio fichero
(`curl -s URL | openssl dgst -sha384 -binary | base64`) o de
https://data.jsdelivr.com/v1/packages/npm/<paquete>@<versión>?structure=flat (sha256), y
comprobar las dos páginas en un navegador sin avisos de CSP en la consola.
"""

import base64
import hashlib
import json
from html import escape

from fastapi.openapi.docs import swagger_ui_default_parameters
from starlette.responses import HTMLResponse

_CDN = "https://cdn.jsdelivr.net/npm"

# swagger-ui-dist 5.34.1 (30 oct 2026) y redoc 2.5.4 (10 sep 2026): las últimas de su
# versión mayor con al menos dos semanas publicadas el 16 nov 2026
SWAGGER_JS = f"{_CDN}/swagger-ui-dist@5.34.1/swagger-ui-bundle.js"
SWAGGER_JS_SRI = "sha384-XFYN47VzPiDY6qPtxYKg0nqUeW/upo20xf1j2SUE7gT/i35FJB4cuS/71Iegzk8Z"
SWAGGER_CSS = f"{_CDN}/swagger-ui-dist@5.34.1/swagger-ui.css"
SWAGGER_CSS_SRI = "sha384-4c3vsE5f+trhFyHrFrLM1fFGUn531NIaC7dcqEWIJdoRQJ5CkJbSuSCwXLpaS1KF"
REDOC_JS = f"{_CDN}/redoc@2.5.4/bundles/redoc.standalone.js"
REDOC_JS_SRI = "sha384-w447zOpYfw/1Tv/5AK9NfHTlQIqE3RVR6KY62jCyy9zNDgO64cMwGGP1Fj0zJVf5"

# Los mismos que ponía FastAPI: el icono de la pestaña y las fuentes de ReDoc
_FAVICON = "https://fastapi.tiangolo.com/img/favicon.png"
_GOOGLE_FONTS = "https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700"

# Los parámetros por defecto de FastAPI, más validatorUrl: null. Sin él, Swagger pinta
# una insignia que es una imagen de validator.swagger.io, que la CSP bloquea (y que
# nunca funcionó: el validador no puede leer un esquema protegido con Basic)
_PARAMETROS_DE_SWAGGER = {**swagger_ui_default_parameters, "validatorUrl": None}

# Fijo, sin nada de la petición dentro: su hash va en la CSP
_ARRANQUE_DE_SWAGGER = (
    "\nconst contenedor = document.getElementById('swagger-ui');\n"
    "window.ui = SwaggerUIBundle(Object.assign("
    f"{json.dumps(_PARAMETROS_DE_SWAGGER, sort_keys=True)}, {{\n"
    "  url: contenedor.dataset.openapiUrl,\n"
    "  presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],\n"
    "}));\n"
)
_HASH_DEL_ARRANQUE = base64.b64encode(
    hashlib.sha256(_ARRANQUE_DE_SWAGGER.encode()).digest()
).decode()

# - script-src: los dos ficheros por su URL completa y el arranque por su hash. Sin
#   'unsafe-eval': las dos páginas, con el esquema entero y el buscador de ReDoc, se
#   probaron en Chrome con esta CSP sin un solo aviso (16 nov 2026).
# - style-src con 'unsafe-inline': Swagger y ReDoc (styled-components) meten <style> y
#   atributos style al pintar. Los estilos no ejecutan código.
# - worker-src blob:: el buscador de ReDoc corre en un worker creado desde un blob.
# - connect-src 'self': piden /openapi.json y, con «Try it out», la propia API.
CSP_DE_LA_DOCUMENTACION = "; ".join(
    [
        "default-src 'none'",
        f"script-src {SWAGGER_JS} {REDOC_JS} 'sha256-{_HASH_DEL_ARRANQUE}'",
        f"style-src {SWAGGER_CSS} https://fonts.googleapis.com 'unsafe-inline'",
        "font-src https://fonts.gstatic.com",
        f"img-src 'self' data: {_FAVICON}",
        "connect-src 'self'",
        "worker-src blob:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)


def pagina_de_swagger(openapi_url: str) -> HTMLResponse:
    """Swagger UI con el esquema de `openapi_url`."""
    return HTMLResponse(
        f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link type="text/css" rel="stylesheet" href="{SWAGGER_CSS}" integrity="{SWAGGER_CSS_SRI}" crossorigin="anonymous">
<link rel="shortcut icon" href="{_FAVICON}">
<title>API Docs</title>
</head>
<body>
<div id="swagger-ui" data-openapi-url="{escape(openapi_url, quote=True)}"></div>
<script src="{SWAGGER_JS}" integrity="{SWAGGER_JS_SRI}" crossorigin="anonymous"></script>
<script>{_ARRANQUE_DE_SWAGGER}</script>
</body>
</html>
"""
    )


def pagina_de_redoc(openapi_url: str) -> HTMLResponse:
    """ReDoc con el esquema de `openapi_url`."""
    return HTMLResponse(
        f"""<!DOCTYPE html>
<html>
<head>
<title>API Docs - ReDoc</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="{_GOOGLE_FONTS}" rel="stylesheet">
<link rel="shortcut icon" href="{_FAVICON}">
<style>
  body {{
    margin: 0;
    padding: 0;
  }}
</style>
</head>
<body>
<noscript>
    ReDoc requires Javascript to function. Please enable it to browse the documentation.
</noscript>
<redoc spec-url="{escape(openapi_url, quote=True)}"></redoc>
<script src="{REDOC_JS}" integrity="{REDOC_JS_SRI}" crossorigin="anonymous"></script>
</body>
</html>
"""
    )
