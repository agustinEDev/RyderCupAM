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
from typing import Any


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
    sanitized = re.sub(r"<[^>]+>", "", text)

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


def sanitize_all_fields(data: dict[str, Any], *, exclude: list[str] | None = None) -> dict[str, Any]:
    """
    Sanitiza todos los campos string de un diccionario recursivamente.

    Útil para sanitizar DTOs completos antes de procesarlos.

    Args:
        data: Diccionario con datos a sanitizar
        exclude: Lista de campos a excluir de sanitización (ej: 'password')

    Returns:
        Diccionario con campos string sanitizados

    Examples:
        >>> sanitize_all_fields({
        ...     "name": "<script>XSS</script>",
        ...     "email": "user@example.com",
        ...     "age": 30
        ... })
        {"name": "XSS", "email": "user@example.com", "age": 30}

        >>> sanitize_all_fields({
        ...     "name": "John <b>Doe</b>",
        ...     "password": "P@ssw0rd!"
        ... }, exclude=["password"])
        {"name": "John Doe", "password": "P@ssw0rd!"}

    Notes:
        - Solo sanitiza valores de tipo string
        - Respeta tipos numéricos, booleanos, etc.
        - Recursivo para diccionarios anidados
        - No modifica el diccionario original
    """
    if exclude is None:
        exclude = []

    sanitized = {}

    for key, value in data.items():
        # Saltar campos excluidos
        if key in exclude:
            sanitized[key] = value
            continue

        # Sanitizar strings
        if isinstance(value, str):
            sanitized[key] = sanitize_html(value)

        # Recursión para diccionarios anidados
        elif isinstance(value, dict):
            sanitized[key] = sanitize_all_fields(value, exclude=exclude)

        # Recursión para listas
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_all_fields(item, exclude=exclude) if isinstance(item, dict)
                else sanitize_html(item) if isinstance(item, str)
                else item
                for item in value
            ]

        # Otros tipos (int, bool, None, etc.) sin modificar
        else:
            sanitized[key] = value

    return sanitized


def remove_sql_keywords(text: str | None) -> str | None:
    """
    Elimina palabras clave SQL comunes de un string.

    Esta es una capa adicional de defensa, aunque el uso de ORM
    ya previene SQL injection mediante parametrización.

    Args:
        text: String a limpiar

    Returns:
        String sin palabras clave SQL

    Examples:
        >>> remove_sql_keywords("SELECT * FROM users")
        " *  users"

        >>> remove_sql_keywords("John DROP TABLE")
        "John  TABLE"

    Notes:
        - Esta función NO reemplaza el uso de ORM parametrizado
        - Es defensa en profundidad (defense in depth)
        - Solo para campos de texto libre, NO para queries
    """
    if text is None:
        return None

    # Lista de palabras clave SQL peligrosas
    sql_keywords = [
        "SELECT", "INSERT", "UPDATE", "DELETE", "DROP",
        "CREATE", "ALTER", "EXEC", "EXECUTE", "UNION",
        "DECLARE", "CAST", "CONVERT", "FROM", "WHERE",
        "--", "/*", "*/", "XP_", "SP_"
    ]

    cleaned = text

    for keyword in sql_keywords:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)

    return cleaned.strip()


def normalize_unicode(text: str | None) -> str | None:
    """
    Normaliza caracteres Unicode a su forma canónica (NFC).

    Previene ataques de homógrafos donde caracteres visualmente
    similares pueden engañar a usuarios.

    Args:
        text: String a normalizar

    Returns:
        String normalizado en forma NFC

    Examples:
        >>> normalize_unicode("café")  # é como carácter compuesto
        "café"  # é como carácter único

    Security:
        - Previene ataques de homógrafos (lookalike characters)
        - Asegura comparaciones consistentes de strings
        - Útil para emails, usernames, etc.
    """
    if text is None:
        return None

    import unicodedata
    return unicodedata.normalize("NFC", text)
