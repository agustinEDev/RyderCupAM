"""
HTTP Context Validator - Shared Infrastructure Layer

Utilidades para validar y extraer información segura del contexto HTTP.

Funcionalidades:
- Validación de direcciones IP (rechaza sentinels, valida formato)
- Validación de User-Agent (rechaza sentinels, valida longitud)
- Extracción segura de IP del cliente con validación de proxy confiable

Security:
- Previene IP spoofing validando headers de proxy contra whitelist
- Rechaza valores sentinel que pueden causar errores ("unknown", "", "0.0.0.0")
- Graceful degradation: retorna None en lugar de lanzar excepciones

Casos de uso:
- Device Fingerprinting (v1.13.0)
- Security Logging (v1.8.0)
- Rate Limiting por IP
- Audit Trail

Patrones: Defensive Programming + Fail-Safe Defaults
"""

import ipaddress
import logging

from fastapi import Request

logger = logging.getLogger(__name__)

# Constantes de validación
MIN_USER_AGENT_LENGTH = 10
MAX_USER_AGENT_LENGTH = 500

# Valores sentinel conocidos que deben ser rechazados
IP_SENTINEL_VALUES = {"unknown", "0.0.0.0", "127.0.0.1", "::1", "localhost"}  # nosec B104
USER_AGENT_SENTINEL_VALUES = {"unknown", ""}


def validate_ip_address(ip: str | None) -> str | None:
    """
    Valida que una dirección IP sea válida y no sea un valor sentinel.

    Esta función es crítica para Device Fingerprinting y Security Logging.
    Previene que valores malformados o sentinel lleguen a DeviceFingerprint.create().

    Args:
        ip: Dirección IP a validar (puede ser None)

    Returns:
        str: IP válida si pasa todas las validaciones
        None: Si IP es inválida, sentinel, o None

    Validaciones aplicadas:
        1. Rechazar None o strings vacíos/whitespace
        2. Rechazar valores sentinel conocidos (unknown, 0.0.0.0, 127.0.0.1, localhost)
        3. Validar formato IP (IPv4 o IPv6) con ipaddress.ip_address()
        4. Rechazar IPs privadas/loopback (opcional - comentado por defecto)

    Examples:
        >>> validate_ip_address("192.168.1.100")
        '192.168.1.100'

        >>> validate_ip_address("unknown")
        None

        >>> validate_ip_address("0.0.0.0")
        None

        >>> validate_ip_address("   ")
        None

        >>> validate_ip_address("not-an-ip")
        None

    Security Notes:
        - NO lanza excepciones (graceful degradation)
        - Logs de advertencia para valores sospechosos
        - Safe para usar en production con datos no confiables
    """
    # 1. Validación básica: None, vacío, whitespace
    if not ip or not ip.strip():
        logger.debug("IP validation failed: empty or None")
        return None

    ip_clean = ip.strip()

    # 2. Rechazar valores sentinel conocidos
    if ip_clean.lower() in IP_SENTINEL_VALUES:
        logger.debug(f"IP validation failed: sentinel value '{ip_clean}'")
        return None

    # 3. Validar formato IP con ipaddress module (IPv4 o IPv6)
    try:
        ip_obj = ipaddress.ip_address(ip_clean)

        # 4. (Opcional) Rechazar IPs privadas/loopback
        # Deshabilitado porque en desarrollo local usamos 192.168.x.x

        return str(ip_obj)  # Normalizado por ipaddress

    except ValueError as e:
        logger.warning(f"IP validation failed: invalid format '{ip_clean}' - {e}")
        return None


def validate_user_agent(user_agent: str | None) -> str | None:
    """
    Valida que un User-Agent sea válido y no sea un valor sentinel.

    Esta función es crítica para Device Fingerprinting.
    Previene que valores malformados lleguen a DeviceFingerprint.create().

    Args:
        user_agent: String del User-Agent HTTP header (puede ser None)

    Returns:
        str: User-Agent válido si pasa todas las validaciones
        None: Si User-Agent es inválido, sentinel, o None

    Validaciones aplicadas:
        1. Rechazar None o strings vacíos/whitespace
        2. Rechazar valores sentinel conocidos ("unknown")
        3. Validar longitud razonable (10-500 caracteres)

    Examples:
        >>> validate_user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...")
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...'

        >>> validate_user_agent("unknown")
        None

        >>> validate_user_agent("   ")
        None

        >>> validate_user_agent("x")  # Muy corto
        None

        >>> validate_user_agent("a" * 1000)  # Muy largo
        None

    Security Notes:
        - NO lanza excepciones (graceful degradation)
        - Límites de longitud previenen ataques de buffer/memoria
        - Safe para usar en production con datos no confiables
    """
    # 1. Validación básica: None, vacío, whitespace
    if not user_agent or not user_agent.strip():
        logger.debug("User-Agent validation failed: empty or None")
        return None

    ua_clean = user_agent.strip()

    # 2. Rechazar valores sentinel conocidos
    if ua_clean.lower() in USER_AGENT_SENTINEL_VALUES:
        logger.debug(f"User-Agent validation failed: sentinel value '{ua_clean}'")
        return None

    # 3. Validar longitud razonable
    if len(ua_clean) < MIN_USER_AGENT_LENGTH:
        logger.debug(
            f"User-Agent validation failed: too short ({len(ua_clean)} < {MIN_USER_AGENT_LENGTH})"
        )
        return None

    if len(ua_clean) > MAX_USER_AGENT_LENGTH:
        logger.warning(
            f"User-Agent validation failed: too long ({len(ua_clean)} > {MAX_USER_AGENT_LENGTH})"
        )
        return None

    return ua_clean


def get_trusted_client_ip(
    request: Request,
    trusted_proxies: list[str] | None = None,
    trust_cloudflare_headers: bool = False,
) -> str | None:
    """
    Extrae la IP del cliente de forma segura validando headers de proxy.

    Esta función previene IP spoofing validando que el request viene de un
    proxy confiable antes de usar headers X-Forwarded-For o X-Real-IP.

    Args:
        request: Request de FastAPI
        trusted_proxies: Lista de IPs de proxies confiables (opcional)
                        Si None, solo usa request.client.host (no confía en headers)
        trust_cloudflare_headers: Si True, confía en CF-Connecting-IP y True-Client-IP
                                 headers. Solo activar si la app está detrás de Cloudflare.
                                 Default: False (seguro por defecto)

    Returns:
        str: IP del cliente validada
        None: Si no se puede determinar una IP válida

    Lógica de extracción (con Cloudflare support):
        1. **Prioridad MÁXIMA:** CF-Connecting-IP (solo si trust_cloudflare_headers=True)
        2. **Prioridad 2:** True-Client-IP (solo si trust_cloudflare_headers=True)
        3. **Prioridad 3:** Si proxy confiable: X-Forwarded-For o X-Real-IP
        4. **Fallback:** request.client.host
        5. Aplicar validate_ip_address() al resultado

    Examples:
        # Caso 1: Request directo (sin proxy)
        >>> get_trusted_client_ip(request, trusted_proxies=None)
        '203.0.113.45'  # request.client.host

        # Caso 2: Request de proxy confiable
        >>> # request viene de 10.0.0.1 (proxy confiable)
        >>> # X-Forwarded-For: "203.0.113.45, 10.0.0.1"
        >>> get_trusted_client_ip(request, trusted_proxies=["10.0.0.1"])
        '203.0.113.45'  # Primera IP del header

        # Caso 3: Request de proxy NO confiable (IP spoofing attempt)
        >>> # request viene de 192.168.1.100 (NO confiable)
        >>> # X-Forwarded-For: "1.2.3.4" (falso)
        >>> get_trusted_client_ip(request, trusted_proxies=["10.0.0.1"])
        '192.168.1.100'  # Ignora header, usa request.client.host

        # Caso 4: App detrás de Cloudflare
        >>> get_trusted_client_ip(request, trust_cloudflare_headers=True)
        '203.0.113.45'  # Usa CF-Connecting-IP

    Security Notes:
        - Previene IP spoofing: NO confía en headers sin validar proxy
        - Cloudflare headers solo se usan si trust_cloudflare_headers=True
        - Usa primera IP de X-Forwarded-For (la del cliente real)
        - Fallback seguro a request.client.host si hay duda
        - Aplica validate_ip_address() al final (rechaza sentinel)
    """
    # 1. Determinar IP del proxy (quien envió el request directamente)
    proxy_ip = request.client.host if request.client else None

    # 2. PRIORIDAD MÁXIMA: Headers de Cloudflare (solo si trust_cloudflare_headers=True)
    # SECURITY: Solo confiar en estos headers si la app está configurada para Cloudflare
    if trust_cloudflare_headers:
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            logger.debug(f"Using CF-Connecting-IP from Cloudflare: {cf_ip.strip()}")
            return validate_ip_address(cf_ip.strip())

        true_client_ip = request.headers.get("True-Client-IP")
        if true_client_ip:
            logger.debug(f"Using True-Client-IP from Cloudflare: {true_client_ip.strip()}")
            return validate_ip_address(true_client_ip.strip())

    # 3. Headers de proxy (solo si proxy es confiable)
    is_trusted_proxy = trusted_proxies and proxy_ip and proxy_ip in trusted_proxies

    if is_trusted_proxy:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            logger.debug(f"Using X-Forwarded-For from trusted proxy: {client_ip}")
            return validate_ip_address(client_ip)

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            logger.debug(f"Using X-Real-IP from trusted proxy: {real_ip.strip()}")
            return validate_ip_address(real_ip.strip())

        logger.debug(f"No proxy headers, using proxy IP: {proxy_ip}")
        return validate_ip_address(proxy_ip)

    # 4. Proxy NO confiable - usar IP directa
    if trusted_proxies and proxy_ip:
        logger.warning(f"Untrusted proxy {proxy_ip} sent request, ignoring forwarded headers")
    else:
        logger.debug(f"Using direct client IP: {proxy_ip}")

    return validate_ip_address(proxy_ip)


def get_user_agent(request: Request) -> str | None:
    """
    Extrae el User-Agent del request de forma segura.

    Wrapper conveniente sobre validate_user_agent() que extrae el header
    User-Agent del request y lo valida automáticamente.

    Args:
        request: Request de FastAPI

    Returns:
        str: User-Agent válido
        None: Si User-Agent es inválido, sentinel, o ausente

    Examples:
        >>> get_user_agent(request)
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...'

        >>> # Request sin User-Agent header
        >>> get_user_agent(request)
        None

    Security Notes:
        - Aplica validate_user_agent() automáticamente
        - Safe para usar en production
        - Graceful degradation (retorna None, no lanza excepciones)
    """
    user_agent = request.headers.get("User-Agent")
    return validate_user_agent(user_agent)
