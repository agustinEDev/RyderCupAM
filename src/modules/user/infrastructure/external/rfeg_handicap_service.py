"""
RFEG Handicap Service - Infrastructure Layer

Implementación concreta del servicio de hándicap usando la API de la RFEG.
Adaptador que encapsula la lógica de scraping del sistema de hándicaps de la
Real Federación Española de Golf.
"""

import re
import unicodedata
from typing import ClassVar

import httpx

from src.modules.user.domain.errors.handicap_errors import (
    HandicapServiceUnavailableError,
)
from src.modules.user.domain.services.handicap_service import HandicapService


class RFEGHandicapService(HandicapService):
    """
    Implementación concreta del servicio de hándicap usando la API de la RFEG.

    Este servicio:
    1. Obtiene un token Bearer dinámicamente de la página principal
    2. Usa ese token para consultar la API de búsqueda de hándicaps
    3. Parsea la respuesta JSON y extrae el hándicap del primer resultado

    La implementación está aislada en la capa de infraestructura,
    permitiendo cambiarla sin afectar la lógica de dominio.
    """

    # Constantes de configuración
    URL_PAGINA_PRINCIPAL = "https://rfegolf.es"
    URL_API_HANDICAP = "https://api.rfeg.es/web/search/handicap"

    # Centinelas para apartar la eñe mientras se borran los diacríticos.
    # Son caracteres de control: no pueden aparecer en un nombre real.
    _CENTINELA_ENIE = "\x00"
    _CENTINELA_ENIE_MAYUSCULA = "\x01"

    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/26.0.1 Safari/605.1.15"
        ),
        "Origin": "https://rfegolf.es",
        "Referer": "https://rfegolf.es/",
    }

    def __init__(self, timeout: int = 10):
        """
        Inicializa el servicio de hándicap RFEG.

        Args:
            timeout: Tiempo máximo de espera para las peticiones HTTP (en segundos)
        """
        self._timeout = timeout

    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        """
        Normaliza un texto eliminando acentos, caracteres diacríticos y espacios extra.

        Útil para búsquedas donde el servicio RFEG puede no encontrar nombres
        con acentos o espacios irregulares (ej: "  José   Pérez  " → "Jose Perez").

        Args:
            texto: Texto a normalizar

        Returns:
            Texto normalizado y limpio
        """
        if not texto:
            return ""

        # 1. Eliminar espacios al principio y al final
        texto_limpio = texto.strip()

        # 2. Reemplazar múltiples espacios por uno solo
        texto_limpio = re.sub(r"\s+", " ", texto_limpio)

        # 3. NFD descompone caracteres acentuados en base + acento
        #    Luego filtramos los caracteres de categoría Mn (Nonspacing_Mark)
        nfd = unicodedata.normalize("NFD", texto_limpio)
        return "".join(char for char in nfd if unicodedata.category(char) != "Mn")

    @classmethod
    def _normalizar_para_comparar(cls, texto: str) -> str:
        """
        Normaliza un nombre para compararlo, preservando la eñe.

        Se diferencia de `_normalizar_texto` en una cosa: mantiene la `ñ`. La eñe
        no es un acento, es una letra distinta, y `Peña` y `Pena` son dos
        apellidos, no dos grafías del mismo. Al comparar la respuesta de la RFEG
        eso importa: el hándicap que casa se persiste sin que nadie lo confirme
        (login, refresco masivo, generación de partidos) y alimenta el reparto de
        golpes, así que casar a dos personas distintas se propaga a los partidos.

        `_normalizar_texto` sigue siendo el correcto para construir la CONSULTA,
        donde quitar la eñe puede ayudar al buscador de la federación.

        Args:
            texto: Nombre a normalizar

        Returns:
            Nombre sin tildes ni espacios extra, pero con sus eñes intactas
        """
        if not texto:
            return ""

        # Se compone a NFC primero: la RFEG podría devolver la eñe ya descompuesta
        # (n + U+0303), y entonces el reemplazo de abajo no la vería.
        texto_nfc = unicodedata.normalize("NFC", texto)

        # La eñe se aparta tras un centinela para que el borrado de diacríticos
        # de `_normalizar_texto` no se la lleve por delante, y se restaura después
        protegido = texto_nfc.replace("ñ", cls._CENTINELA_ENIE).replace(
            "Ñ", cls._CENTINELA_ENIE_MAYUSCULA
        )
        normalizado = cls._normalizar_texto(protegido)
        return normalizado.replace(cls._CENTINELA_ENIE, "ñ").replace(
            cls._CENTINELA_ENIE_MAYUSCULA, "Ñ"
        )

    async def search_handicap(self, full_name: str) -> float | None:
        """
        Busca el hándicap de un jugador en la RFEG.

        Intenta primero con el nombre original y si no encuentra resultados,
        reintenta con el nombre normalizado (sin acentos).

        El reintento NO existe para casar la respuesta: eso lo resuelve ya
        `_buscar_en_api`, que compara normalizado contra normalizado. Se mantiene
        porque el buscador de la RFEG puede devolver un conjunto de resultados
        distinto según la consulta lleve tildes o no, que es una pregunta sobre su
        motor y no sobre cómo comparamos. Solo dos llamadas reales pueden zanjarla;
        hasta entonces se queda, porque quitarlo sería una apuesta sin datos.

        Args:
            full_name: Nombre completo del jugador (ej: "Juan Pérez García")

        Returns:
            Hándicap del jugador o None si no se encuentra

        Raises:
            HandicapServiceUnavailableError: Si el servicio no está disponible
        """
        try:
            # 1. Obtener token Bearer dinámicamente
            bearer_token = await self._obtener_bearer_token()
            if not bearer_token:
                raise HandicapServiceUnavailableError(
                    "No se pudo obtener el token de autenticación de la RFEG"
                )

            # 2. Buscar jugador primero con nombre original
            handicap = await self._buscar_en_api(full_name, bearer_token)
            if handicap is not None:
                return handicap

            # 3. Si no se encontró, reintentar con nombre normalizado por si la
            #    RFEG devuelve otros resultados para la consulta sin acentos
            nombre_normalizado = self._normalizar_texto(full_name)
            if nombre_normalizado != full_name:
                return await self._buscar_en_api(
                    nombre_normalizado, bearer_token, nombre_real=full_name
                )

            return None

        except httpx.HTTPError as e:
            raise HandicapServiceUnavailableError(
                f"Error de conexión con el servicio RFEG: {e}"
            ) from e

    async def _obtener_bearer_token(self) -> str | None:
        """
        Obtiene el token Bearer extrayéndolo de la página principal.

        El token se encuentra en el código JavaScript de la página
        y tiene el formato 'coded_[hexadecimal]'.

        Returns:
            Token en formato "Bearer {token}" o None si no se encuentra
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.URL_PAGINA_PRINCIPAL, headers=self.HEADERS, timeout=self._timeout
            )
            response.raise_for_status()

            # Buscar token en el HTML usando regex
            # Patrón: 'coded_' seguido de caracteres hexadecimales (longitud variable)
            match = re.search(r"'coded_[0-9a-fA-F]{32,}'", response.text)
            if match:
                token = match.group(0).strip("'")
                return f"Bearer {token}"

            return None

    async def _buscar_en_api(
        self, consulta: str, bearer_token: str, nombre_real: str | None = None
    ) -> float | None:
        """
        Realiza la búsqueda en la API de la RFEG.

        La consulta que se envía y el nombre contra el que se comparan las
        respuestas son dos cosas distintas: el reintento manda el nombre sin
        acentos para ayudar al buscador de la federación, pero comparar contra esa
        misma consulta despojada reintroduciría los falsos positivos que este
        cambio corrige (un `Pena` casando con un `Peña`). Se compara siempre
        contra lo que el jugador escribió de verdad.

        Args:
            consulta: Texto que se envía a la RFEG como término de búsqueda
            bearer_token: Token de autorización en formato "Bearer {token}"
            nombre_real: Nombre del jugador contra el que comparar las respuestas.
                Si no se indica, se compara contra la propia consulta.

        Returns:
            Hándicap del primer resultado encontrado o None
        """
        # Preparar headers con el token de autorización
        api_headers = self.HEADERS.copy()
        api_headers.update(
            {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Authorization": bearer_token,
            }
        )

        # Parámetros de búsqueda
        params = {"q": consulta}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.URL_API_HANDICAP,
                params=params,
                headers=api_headers,
                timeout=self._timeout,
            )
            response.raise_for_status()

            datos = response.json()

            # Buscar coincidencia exacta en todos los resultados
            # La API de RFEG devuelve la estructura: {"data": {"hits": [{"document": {...}}]}}
            #
            # La comparación se hace sobre el texto normalizado a ambos lados: la
            # federación guarda los nombres con sus tildes y el jugador puede
            # escribirlos sin ellas (o al revés). Comparar en literal hacía fallar
            # la búsqueda en cuanto las dos grafías no coincidían exactamente.
            if datos and "data" in datos:
                hits = datos["data"].get("hits") or []
                nombre_buscado = self._normalizar_para_comparar(
                    nombre_real if nombre_real is not None else consulta
                ).upper()

                for hit in hits:
                    jugador = (hit or {}).get("document") or {}
                    nombre_encontrado = self._normalizar_para_comparar(
                        jugador.get("full_name") or ""
                    ).upper()

                    if nombre_encontrado and nombre_encontrado == nombre_buscado:
                        handicap = jugador.get("handicap")
                        if handicap is None:
                            continue
                        try:
                            return float(handicap)
                        except (TypeError, ValueError):
                            # La RFEG puede devolver el hándicap como texto no
                            # numérico ("N/A", "-", "15,4"). Sin esto la excepción
                            # escapa del `except httpx.HTTPError` de search_handicap
                            # y sale como un 500 en vez de "no encontrado".
                            continue

            return None
