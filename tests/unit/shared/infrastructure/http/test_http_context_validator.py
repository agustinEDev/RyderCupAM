"""
Tests para HTTP Context Validator - Shared Infrastructure Layer

Tests de las funciones de validación HTTP segura:
- validate_ip_address()
- validate_user_agent()
- get_trusted_client_ip()
- get_user_agent()

Cobertura:
- Validación de valores sentinel
- Validación de formato
- Prevención de IP spoofing
- Graceful degradation (retorna None, no lanza excepciones)

Patrón: Given-When-Then + Pytest Fixtures
"""

import pytest
from unittest.mock import Mock
from fastapi import Request

from src.shared.infrastructure.http.http_context_validator import (
    validate_ip_address,
    validate_user_agent,
    get_trusted_client_ip,
    get_user_agent,
)


# ============================================================================
# TEST SUITE: validate_ip_address()
# ============================================================================


class TestValidateIPAddress:
    """
    Test Suite para validate_ip_address().

    Casos de prueba:
    - IPs válidas (IPv4, IPv6)
    - Valores sentinel (unknown, 0.0.0.0, 127.0.0.1, localhost)
    - Valores vacíos/None/whitespace
    - Formatos inválidos
    - Normalización de IPs
    """

    def test_validate_ipv4_valid(self):
        """
        Given: Una dirección IPv4 válida
        When: validate_ip_address() es llamada
        Then: Retorna la IP normalizada
        """
        # Given
        ip = "192.168.1.100"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result == "192.168.1.100"

    def test_validate_ipv6_valid(self):
        """
        Given: Una dirección IPv6 válida
        When: validate_ip_address() es llamada
        Then: Retorna la IP normalizada
        """
        # Given
        ip = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result == "2001:db8:85a3::8a2e:370:7334"  # Normalizada por ipaddress

    def test_validate_ip_sentinel_unknown(self):
        """
        Given: Valor sentinel "unknown"
        When: validate_ip_address() es llamada
        Then: Retorna None
        """
        # Given
        ip = "unknown"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_sentinel_zero(self):
        """
        Given: Valor sentinel "0.0.0.0"
        When: validate_ip_address() es llamada
        Then: Retorna None
        """
        # Given
        ip = "0.0.0.0"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_sentinel_localhost(self):
        """
        Given: Valor sentinel "127.0.0.1"
        When: validate_ip_address() es llamada
        Then: Retorna None
        """
        # Given
        ip = "127.0.0.1"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_sentinel_ipv6_localhost(self):
        """
        Given: Valor sentinel "::1" (IPv6 localhost)
        When: validate_ip_address() es llamada
        Then: Retorna None
        """
        # Given
        ip = "::1"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_sentinel_localhost_name(self):
        """
        Given: Valor sentinel "localhost"
        When: validate_ip_address() es llamada
        Then: Retorna None
        """
        # Given
        ip = "localhost"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_empty_string(self):
        """
        Given: String vacío
        When: validate_ip_address() es llamada
        Then: Retorna None
        """
        # Given
        ip = ""

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_none(self):
        """
        Given: None
        When: validate_ip_address() es llamada
        Then: Retorna None
        """
        # Given
        ip = None

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_whitespace(self):
        """
        Given: Solo whitespace "   "
        When: validate_ip_address() es llamada
        Then: Retorna None
        """
        # Given
        ip = "   "

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_invalid_format(self):
        """
        Given: Formato inválido "not-an-ip"
        When: validate_ip_address() es llamada
        Then: Retorna None (NO lanza excepción)
        """
        # Given
        ip = "not-an-ip"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_invalid_format_numbers(self):
        """
        Given: Formato inválido "999.999.999.999"
        When: validate_ip_address() es llamada
        Then: Retorna None (NO lanza excepción)
        """
        # Given
        ip = "999.999.999.999"

        # When
        result = validate_ip_address(ip)

        # Then
        assert result is None

    def test_validate_ip_strips_whitespace(self):
        """
        Given: IP válida con whitespace "  192.168.1.100  "
        When: validate_ip_address() es llamada
        Then: Retorna IP sin whitespace
        """
        # Given
        ip = "  192.168.1.100  "

        # When
        result = validate_ip_address(ip)

        # Then
        assert result == "192.168.1.100"


# ============================================================================
# TEST SUITE: validate_user_agent()
# ============================================================================


class TestValidateUserAgent:
    """
    Test Suite para validate_user_agent().

    Casos de prueba:
    - User-Agent válidos
    - Valores sentinel (unknown, "")
    - Valores vacíos/None/whitespace
    - Longitudes inválidas (muy corto, muy largo)
    - Normalización (trim whitespace)
    """

    def test_validate_user_agent_valid(self):
        """
        Given: User-Agent válido
        When: validate_user_agent() es llamada
        Then: Retorna el User-Agent
        """
        # Given
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

        # When
        result = validate_user_agent(ua)

        # Then
        assert result == ua

    def test_validate_user_agent_sentinel_unknown(self):
        """
        Given: Valor sentinel "unknown"
        When: validate_user_agent() es llamada
        Then: Retorna None
        """
        # Given
        ua = "unknown"

        # When
        result = validate_user_agent(ua)

        # Then
        assert result is None

    def test_validate_user_agent_empty_string(self):
        """
        Given: String vacío
        When: validate_user_agent() es llamada
        Then: Retorna None
        """
        # Given
        ua = ""

        # When
        result = validate_user_agent(ua)

        # Then
        assert result is None

    def test_validate_user_agent_none(self):
        """
        Given: None
        When: validate_user_agent() es llamada
        Then: Retorna None
        """
        # Given
        ua = None

        # When
        result = validate_user_agent(ua)

        # Then
        assert result is None

    def test_validate_user_agent_whitespace(self):
        """
        Given: Solo whitespace "   "
        When: validate_user_agent() es llamada
        Then: Retorna None
        """
        # Given
        ua = "   "

        # When
        result = validate_user_agent(ua)

        # Then
        assert result is None

    def test_validate_user_agent_too_short(self):
        """
        Given: User-Agent muy corto (< 10 caracteres)
        When: validate_user_agent() es llamada
        Then: Retorna None
        """
        # Given
        ua = "Chrome"  # 6 caracteres

        # When
        result = validate_user_agent(ua)

        # Then
        assert result is None

    def test_validate_user_agent_too_long(self):
        """
        Given: User-Agent muy largo (> 500 caracteres)
        When: validate_user_agent() es llamada
        Then: Retorna None
        """
        # Given
        ua = "x" * 501

        # When
        result = validate_user_agent(ua)

        # Then
        assert result is None

    def test_validate_user_agent_strips_whitespace(self):
        """
        Given: User-Agent válido con whitespace
        When: validate_user_agent() es llamada
        Then: Retorna User-Agent sin whitespace
        """
        # Given
        ua = "  Mozilla/5.0 (Windows NT 10.0)  "

        # When
        result = validate_user_agent(ua)

        # Then
        assert result == "Mozilla/5.0 (Windows NT 10.0)"

    def test_validate_user_agent_minimum_length(self):
        """
        Given: User-Agent con longitud mínima (10 caracteres)
        When: validate_user_agent() es llamada
        Then: Retorna el User-Agent
        """
        # Given
        ua = "1234567890"  # Exactamente 10 caracteres

        # When
        result = validate_user_agent(ua)

        # Then
        assert result == ua

    def test_validate_user_agent_maximum_length(self):
        """
        Given: User-Agent con longitud máxima (500 caracteres)
        When: validate_user_agent() es llamada
        Then: Retorna el User-Agent
        """
        # Given
        ua = "x" * 500  # Exactamente 500 caracteres

        # When
        result = validate_user_agent(ua)

        # Then
        assert result == ua


# ============================================================================
# TEST SUITE: get_trusted_client_ip()
# ============================================================================


class TestGetTrustedClientIP:
    """
    Test Suite para get_trusted_client_ip().

    Casos de prueba:
    - Proxy confiable con X-Forwarded-For
    - Proxy confiable con X-Real-IP
    - Proxy NO confiable (ignora headers)
    - Sin configuración de proxies confiables
    - Validación de IPs extraídas
    - Múltiples IPs en X-Forwarded-For
    """

    def test_trusted_proxy_with_forwarded_for(self):
        """
        Given: Request de proxy confiable con X-Forwarded-For
        When: get_trusted_client_ip() es llamada
        Then: Retorna la primera IP del header (IP del cliente real)
        """
        # Given
        request = Mock(spec=Request)
        request.client = Mock(host="10.0.0.1")  # IP del proxy
        request.headers = {"X-Forwarded-For": "203.0.113.45, 10.0.0.1"}

        trusted_proxies = ["10.0.0.1"]

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result == "203.0.113.45"

    def test_trusted_proxy_with_real_ip(self):
        """
        Given: Request de proxy confiable con X-Real-IP (sin X-Forwarded-For)
        When: get_trusted_client_ip() es llamada
        Then: Retorna la IP del header X-Real-IP
        """
        # Given
        request = Mock(spec=Request)
        request.client = Mock(host="10.0.0.1")  # IP del proxy
        request.headers = {"X-Real-IP": "203.0.113.45"}

        trusted_proxies = ["10.0.0.1"]

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result == "203.0.113.45"

    def test_untrusted_proxy_ignores_headers(self):
        """
        Given: Request de proxy NO confiable con X-Forwarded-For falso
        When: get_trusted_client_ip() es llamada
        Then: Retorna la IP del proxy (ignora header)
        """
        # Given
        request = Mock(spec=Request)
        request.client = Mock(host="192.168.1.100")  # IP NO confiable
        request.headers = {"X-Forwarded-For": "1.2.3.4"}  # Intento de spoofing

        trusted_proxies = ["10.0.0.1"]  # Solo confía en 10.0.0.1

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result == "192.168.1.100"  # IP real del cliente, NO la del header

    def test_no_trusted_proxies_configured(self):
        """
        Given: Sin configuración de proxies confiables
        When: get_trusted_client_ip() es llamada
        Then: Retorna request.client.host (NO confía en headers)
        """
        # Given
        request = Mock(spec=Request)
        request.client = Mock(host="203.0.113.45")
        request.headers = {"X-Forwarded-For": "1.2.3.4"}  # Ignorado

        trusted_proxies = []  # Sin proxies confiables

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result == "203.0.113.45"  # Usa client.host, ignora headers

    def test_no_trusted_proxies_none(self):
        """
        Given: trusted_proxies=None (sin configuración)
        When: get_trusted_client_ip() es llamada
        Then: Retorna request.client.host (NO confía en headers)
        """
        # Given
        request = Mock(spec=Request)
        request.client = Mock(host="203.0.113.45")
        request.headers = {"X-Forwarded-For": "1.2.3.4"}  # Ignorado

        trusted_proxies = None  # Sin proxies confiables

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result == "203.0.113.45"  # Usa client.host, ignora headers

    def test_multiple_ips_in_forwarded_for(self):
        """
        Given: X-Forwarded-For con múltiples IPs "client, proxy1, proxy2"
        When: get_trusted_client_ip() es llamada
        Then: Retorna la primera IP (cliente real)
        """
        # Given
        request = Mock(spec=Request)
        request.client = Mock(host="10.0.0.3")  # Último proxy
        request.headers = {"X-Forwarded-For": "203.0.113.45, 10.0.0.1, 10.0.0.2"}

        trusted_proxies = ["10.0.0.3"]

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result == "203.0.113.45"  # Primera IP (cliente)

    def test_validates_extracted_ip(self):
        """
        Given: Proxy confiable con X-Forwarded-For conteniendo IP inválida
        When: get_trusted_client_ip() es llamada
        Then: Retorna None (validate_ip_address() rechaza la IP)
        """
        # Given
        request = Mock(spec=Request)
        request.client = Mock(host="10.0.0.1")
        request.headers = {"X-Forwarded-For": "unknown"}  # Valor sentinel

        trusted_proxies = ["10.0.0.1"]

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result is None  # validate_ip_address() rechazó "unknown"

    def test_no_client_host(self):
        """
        Given: Request sin request.client.host
        When: get_trusted_client_ip() es llamada
        Then: Retorna None
        """
        # Given
        request = Mock(spec=Request)
        request.client = None
        request.headers = {}

        trusted_proxies = []

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result is None

    def test_trusted_proxy_no_headers(self):
        """
        Given: Proxy confiable pero sin headers X-Forwarded-For/X-Real-IP
        When: get_trusted_client_ip() es llamada
        Then: Retorna la IP del proxy (conexión directa al proxy)
        """
        # Given
        request = Mock(spec=Request)
        request.client = Mock(host="10.0.0.1")
        request.headers = {}  # Sin headers de proxy

        trusted_proxies = ["10.0.0.1"]

        # When
        result = get_trusted_client_ip(request, trusted_proxies)

        # Then
        assert result == "10.0.0.1"  # Usa la IP del proxy


# ============================================================================
# TEST SUITE: get_user_agent()
# ============================================================================


class TestGetUserAgent:
    """
    Test Suite para get_user_agent().

    Casos de prueba:
    - User-Agent válido en headers
    - Sin User-Agent en headers
    - User-Agent inválido (sentinel)
    - Validación automática
    """

    def test_get_user_agent_valid(self):
        """
        Given: Request con User-Agent válido
        When: get_user_agent() es llamada
        Then: Retorna el User-Agent validado
        """
        # Given
        request = Mock(spec=Request)
        request.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}

        # When
        result = get_user_agent(request)

        # Then
        assert result == "Mozilla/5.0 (Windows NT 10.0)"

    def test_get_user_agent_missing(self):
        """
        Given: Request sin User-Agent header
        When: get_user_agent() es llamada
        Then: Retorna None
        """
        # Given
        request = Mock(spec=Request)
        request.headers = {}

        # When
        result = get_user_agent(request)

        # Then
        assert result is None

    def test_get_user_agent_invalid_sentinel(self):
        """
        Given: Request con User-Agent="unknown" (sentinel)
        When: get_user_agent() es llamada
        Then: Retorna None (validate_user_agent() lo rechaza)
        """
        # Given
        request = Mock(spec=Request)
        request.headers = {"User-Agent": "unknown"}

        # When
        result = get_user_agent(request)

        # Then
        assert result is None

    def test_get_user_agent_too_short(self):
        """
        Given: Request con User-Agent muy corto
        When: get_user_agent() es llamada
        Then: Retorna None (validate_user_agent() lo rechaza)
        """
        # Given
        request = Mock(spec=Request)
        request.headers = {"User-Agent": "short"}

        # When
        result = get_user_agent(request)

        # Then
        assert result is None
