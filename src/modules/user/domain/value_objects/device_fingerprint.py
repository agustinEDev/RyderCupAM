"""
Value Object para la huella digital de un dispositivo.

Este módulo define DeviceFingerprint, un VO que crea una identificación
única del dispositivo basada en User-Agent e IP, con hash SHA256 para
privacidad.

Responsabilidades:
- Generar hash seguro (SHA256) del fingerprint
- Parsear User-Agent para extraer navegador y OS
- Generar nombres legibles de dispositivos automáticamente
- Normalizar direcciones IP (IPv6 → IPv4)
- Garantizar inmutabilidad y comparación por valor

Características:
- No almacena IPs en texto plano (solo hash)
- Parsing inteligente de User-Agent
- Nombres auto-generados legibles ("Chrome on macOS")
- Normalización de IPs para consistencia
"""

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceFingerprint:
    """
    Value Object que representa la huella digital única de un dispositivo.

    Combina User-Agent e IP para crear un identificador único que:
    - Detecta el mismo dispositivo en futuros logins
    - Protege privacidad (hash en vez de IP plana)
    - Genera nombres automáticos legibles

    Attributes:
        user_agent (str): String del User-Agent del navegador
        ip_address (str): Dirección IP del cliente
        fingerprint_hash (str): Hash SHA256 de user_agent + ip
        device_name (str): Nombre auto-generado ("Chrome on macOS")

    Examples:
        >>> fp = DeviceFingerprint.create(
        ...     user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
        ...     ip_address="192.168.1.100"
        ... )
        >>> fp.device_name
        'Chrome on macOS'
        >>> len(fp.fingerprint_hash)
        64  # SHA256 hex
    """

    user_agent: str
    ip_address: str
    fingerprint_hash: str
    device_name: str

    @staticmethod
    def create(user_agent: str, ip_address: str) -> "DeviceFingerprint":
        """
        Crea un DeviceFingerprint a partir de User-Agent e IP.

        Este es el método principal para crear fingerprints. Automáticamente:
        1. Normaliza la IP (convierte IPv6 a IPv4 si es posible)
        2. Genera el hash SHA256 del fingerprint
        3. Parsea el User-Agent para generar nombre legible

        Args:
            user_agent: String del User-Agent HTTP header
            ip_address: Dirección IP del cliente (IPv4 o IPv6)

        Returns:
            DeviceFingerprint: Nuevo fingerprint con hash y nombre generados

        Raises:
            ValueError: Si user_agent o ip_address están vacíos

        Examples:
            >>> fp = DeviceFingerprint.create(
            ...     user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)...",
            ...     ip_address="10.0.2.15"
            ... )
            >>> fp.device_name
            'Safari on iOS'
        """
        # Validaciones
        if not user_agent or not user_agent.strip():
            raise ValueError("User-Agent no puede estar vacío")
        if not ip_address or not ip_address.strip():
            raise ValueError("IP address no puede estar vacía")

        # Normalizar IP (IPv6 → IPv4 si es mapping)
        normalized_ip = DeviceFingerprint._normalize_ip(ip_address)

        # Generar hash SHA256
        fingerprint_str = f"{user_agent.strip()}|{normalized_ip}"
        hash_value = hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()

        # Generar nombre legible
        device_name = DeviceFingerprint._generate_device_name(user_agent, normalized_ip)

        return DeviceFingerprint(
            user_agent=user_agent.strip(),
            ip_address=normalized_ip,
            fingerprint_hash=hash_value,
            device_name=device_name,
        )

    @staticmethod
    def _normalize_ip(ip_address: str) -> str:
        """
        Normaliza direcciones IP para consistencia.

        Convierte IPv6-mapped-IPv4 (::ffff:192.168.1.1) a IPv4 puro (192.168.1.1).
        Esto garantiza que el mismo dispositivo con diferentes formatos de IP
        genere el mismo fingerprint.

        Args:
            ip_address: Dirección IP original (puede ser IPv4 o IPv6)

        Returns:
            str: IP normalizada

        Examples:
            >>> DeviceFingerprint._normalize_ip("::ffff:192.168.1.100")
            '192.168.1.100'
            >>> DeviceFingerprint._normalize_ip("192.168.1.100")
            '192.168.1.100'
        """
        ip_clean = ip_address.strip()

        # Convertir IPv6-mapped-IPv4 a IPv4 puro
        if ip_clean.startswith("::ffff:"):
            return ip_clean.replace("::ffff:", "")

        return ip_clean

    @staticmethod
    def _generate_device_name(user_agent: str, ip_address: str) -> str:
        """
        Genera un nombre legible automáticamente desde el User-Agent.

        Parsea el User-Agent para extraer:
        - Navegador (Chrome, Firefox, Safari, Edge, etc.)
        - Sistema Operativo (Windows, macOS, Linux, iOS, Android)
        - Versión mayor del OS (opcional)

        Formato: "{Browser} on {OS}" (ej: "Chrome on macOS")

        Args:
            user_agent: String del User-Agent
            ip_address: IP (usada para mostrar últimos dígitos como fallback)

        Returns:
            str: Nombre legible del dispositivo

        Examples:
            >>> ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"
            >>> DeviceFingerprint._generate_device_name(ua, "192.168.1.100")
            'Chrome on macOS'

            >>> ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
            >>> DeviceFingerprint._generate_device_name(ua, "10.0.2.15")
            'Safari on iOS'
        """
        # Detectar navegador
        browser = DeviceFingerprint._parse_browser(user_agent)

        # Detectar sistema operativo
        os_name = DeviceFingerprint._parse_os(user_agent)

        # Fallback si no se pudo parsear
        if browser == "Unknown" and os_name == "Unknown":
            # Últimos 3 dígitos de la IP como identificador
            ip_suffix = ip_address.split(".")[-1] if "." in ip_address else "xxx"
            return f"Unknown Device (IP: ...{ip_suffix})"

        return f"{browser} on {os_name}"

    @staticmethod
    def _parse_browser(user_agent: str) -> str:
        """
        Extrae el nombre del navegador del User-Agent.

        Detecta navegadores comunes con orden de prioridad
        (importante: Edge antes de Chrome, ya que Edge contiene "Chrome").

        Args:
            user_agent: String del User-Agent

        Returns:
            str: Nombre del navegador o "Unknown"

        Examples:
            >>> DeviceFingerprint._parse_browser("...Chrome/120.0...")
            'Chrome'
            >>> DeviceFingerprint._parse_browser("...Firefox/118.0...")
            'Firefox'
        """
        ua_lower = user_agent.lower()

        # Orden importante: Edge antes de Chrome (Edge incluye "chrome" en su UA)
        if "edg/" in ua_lower or "edge/" in ua_lower:
            return "Edge"
        if "chrome/" in ua_lower:
            # Chrome puede o no incluir "Safari/" dependiendo del contexto
            return "Chrome"
        if "firefox/" in ua_lower:
            return "Firefox"
        if "safari/" in ua_lower:
            # Safari puro (sin Chrome en el UA)
            return "Safari"
        if "opera/" in ua_lower or "opr/" in ua_lower:
            return "Opera"

        return "Unknown"

    @staticmethod
    def _parse_os(user_agent: str) -> str:  # noqa: PLR0911
        """
        Extrae el sistema operativo del User-Agent.

        Detecta sistemas operativos comunes con orden de prioridad.

        Args:
            user_agent: String del User-Agent

        Returns:
            str: Nombre del OS o "Unknown"

        Examples:
            >>> DeviceFingerprint._parse_os("...Macintosh; Intel Mac OS X 10_15_7...")
            'macOS'
            >>> DeviceFingerprint._parse_os("...iPhone; CPU iPhone OS 16_0...")
            'iOS'
        """
        ua_lower = user_agent.lower()

        # Mobile primero (más específico)
        if "iphone" in ua_lower or "ipad" in ua_lower:
            return "iOS"
        if "android" in ua_lower:
            return "Android"

        # Desktop
        if "macintosh" in ua_lower or "mac os x" in ua_lower:
            return "macOS"
        if "windows" in ua_lower:
            # Extraer versión si es posible
            version_match = re.search(r"windows nt (\d+\.\d+)", ua_lower)
            if version_match:
                version = version_match.group(1)
                # Mapeo de versiones conocidas
                version_map = {
                    "10.0": "Windows 10/11",
                    "6.3": "Windows 8.1",
                    "6.2": "Windows 8",
                    "6.1": "Windows 7",
                }
                return version_map.get(version, "Windows")
            return "Windows"
        if "linux" in ua_lower and "android" not in ua_lower:
            return "Linux"

        return "Unknown"

    def matches(self, other: "DeviceFingerprint") -> bool:
        """
        Verifica si este fingerprint representa el mismo dispositivo que otro.

        Compara los hashes SHA256. Si coinciden, es el mismo dispositivo
        (mismo User-Agent + IP).

        Args:
            other: Otro DeviceFingerprint a comparar

        Returns:
            bool: True si es el mismo dispositivo, False en caso contrario

        Examples:
            >>> fp1 = DeviceFingerprint.create("Mozilla/5.0...", "192.168.1.100")
            >>> fp2 = DeviceFingerprint.create("Mozilla/5.0...", "192.168.1.100")
            >>> fp1.matches(fp2)
            True
        """
        return self.fingerprint_hash == other.fingerprint_hash

    def __eq__(self, other: object) -> bool:
        """
        Compara dos DeviceFingerprint por valor.

        Dos fingerprints son iguales si sus hashes coinciden.

        Args:
            other: Otro objeto a comparar

        Returns:
            bool: True si son iguales, False en caso contrario
        """
        if not isinstance(other, DeviceFingerprint):
            return False
        return self.fingerprint_hash == other.fingerprint_hash

    def __hash__(self) -> int:
        """
        Genera hash del DeviceFingerprint.

        Permite usar DeviceFingerprint como clave de diccionario.

        Returns:
            int: Hash del fingerprint_hash
        """
        return hash(self.fingerprint_hash)

    def __str__(self) -> str:
        """
        Representación legible del DeviceFingerprint.

        Returns:
            str: Nombre del dispositivo
        """
        return self.device_name

    def __repr__(self) -> str:
        """
        Representación técnica para debugging.

        Returns:
            str: Representación completa con hash truncado
        """
        hash_preview = self.fingerprint_hash[:16] + "..."
        return f"DeviceFingerprint(device_name='{self.device_name}', hash='{hash_preview}')"
