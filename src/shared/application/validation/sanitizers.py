"""
HTML Sanitizers - Sanitización de inputs para prevenir XSS

Proporciona funciones para sanitizar strings de entrada eliminando
o escapando HTML, JavaScript y otros contenidos peligrosos.

OWASP Coverage:
- A03: Injection (prevención de XSS mediante sanitización)
- A04: Insecure Design (validación defensiva de inputs)

Estrategia:
- Strip ALL HTML por defecto (más seguro)
- No permitir ningún tag HTML en inputs de usuario
- Whitespace normalizado
"""

import html
import re


def sanitize_html(text: str | None, *, allow_whitespace: bool = True) -> str | None:
    """
    Sanitiza un string eliminando TODO el HTML y normalizando espacios.

    Esta función implementa una estrategia de "denegar todo" que es
    la más segura para prevenir ataques XSS.

    Args:
        text: String a sanitizar (puede ser None)
        allow_whitespace: Si True, normaliza espacios múltiples a uno solo

    Returns:
        String sanitizado o None si el input era None

    Estrategia de Sanitización:
        1. Escape de entidades HTML (&lt; &gt; etc.)
        2. Eliminación de tags HTML residuales
        3. Normalización de espacios múltiples
        4. Trim de espacios al inicio/final

    Examples:
        >>> sanitize_html("<script>alert('XSS')</script>")
        "alert('XSS')"

        >>> sanitize_html("John <b>Doe</b>")
        "John Doe"

        >>> sanitize_html("Test    multiple   spaces")
        "Test multiple spaces"

        >>> sanitize_html(None)
        None

    Security Notes:
        - NO permite ningún HTML (más seguro que whitelist)
        - Escapa entidades HTML automáticamente
        - Previene XSS stored y reflected
    """
    if text is None:
        return None

    # Si el string está vacío o solo tiene espacios, retornar vacío
    if not text.strip():
        return ""

    # 1. Eliminar cualquier tag HTML PRIMERO (antes de escape)
    # Regex para detectar patrones como <tag>, </tag>, <tag attr="value">
    # Uses [^<>]+ (not [^>]+) to prevent polynomial backtracking (ReDoS)
    sanitized = re.sub(r"<[^<>]+>", "", text)

    # 2. Escape de entidades HTML existentes
    # Esto convierte < a &lt;, > a &gt;, etc.
    sanitized = html.escape(sanitized, quote=False)

    # 3. Eliminar caracteres de control peligrosos (NULL bytes, etc.)
    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", sanitized)

    # 4. Normalizar espacios múltiples a uno solo (si está habilitado)
    if allow_whitespace:
        sanitized = re.sub(r"\s+", " ", sanitized)

    # 5. Trim espacios al inicio y final
    sanitized = sanitized.strip()

    return sanitized
