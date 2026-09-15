"""
RFEG Handicap Service - Infrastructure Layer

Implementación concreta del servicio de hándicap usando la API de la RFEG.
Adaptador que encapsula la lógica de scraping del sistema de hándicaps de la
Real Federación Española de Golf.
"""

import logging
import re
import unicodedata
from typing import ClassVar

import httpx

from src.modules.user.domain.errors.handicap_errors import (
    HandicapServiceUnavailableError,
)
from src.modules.user.domain.services.handicap_service import HandicapService

logger = logging.getLogger(__name__)


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

        Una sola consulta: el buscador de la federación ya ignora los diacríticos
        —medido con cuatro pares de nombres, resultados idénticos con y sin
        tildes—, así que reintentar sin acentos gastaba una petición de más para
        recibir lo mismo. Que la grafía del jugador y la de la RFEG no coincidan
        lo resuelve `_buscar_en_api`, comparando normalizado contra normalizado.

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

            # 2. Buscar al jugador
            return await self._buscar_en_api(full_name, bearer_token)

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

    @staticmethod
    def _extraer_jugadores(datos: object) -> list[dict]:
        """
        Valida la forma de la respuesta y devuelve los documentos de jugador.

        Todo lo que llega de la RFEG pasa por aquí. Leer la estructura a pelo
        (`datos["data"].get("hits")`) lanza `AttributeError` o `TypeError` en
        cuanto la federación devuelve otra forma, y esas excepciones no son
        `httpx.HTTPError`: se escapan de `search_handicap` y salen como un 500,
        cuando lo que de verdad ha pasado es que el servicio no responde lo
        acordado. Un contenedor con forma inesperada se trata como servicio no
        disponible; un elemento suelto que no encaja se descarta con un aviso,
        porque no invalida al resto de la respuesta.

        Args:
            datos: Cuerpo ya parseado de la respuesta de la RFEG

        Returns:
            Los documentos de jugador, o lista vacía si no hubo resultados

        Raises:
            HandicapServiceUnavailableError: Si la respuesta no tiene la forma
                documentada: {"data": {"hits": [{"document": {...}}]}}
        """

        def no_disponible(detalle: str) -> HandicapServiceUnavailableError:
            return HandicapServiceUnavailableError(
                f"La RFEG devolvió una respuesta con forma inesperada: {detalle}"
            )

        if not datos:
            return []
        if not isinstance(datos, dict):
            raise no_disponible(f"la raíz es {type(datos).__name__}, no un objeto")

        contenedor = datos.get("data")
        if not contenedor:
            return []
        if not isinstance(contenedor, dict):
            raise no_disponible(f"'data' es {type(contenedor).__name__}, no un objeto")

        hits = contenedor.get("hits") or []
        if not isinstance(hits, list):
            raise no_disponible(f"'hits' es {type(hits).__name__}, no una lista")

        jugadores = []
        for hit in hits:
            if not isinstance(hit, dict):
                logger.warning("Resultado descartado, no es un objeto: %r", hit)
                continue
            jugador = hit.get("document") or {}
            if not isinstance(jugador, dict):
                logger.warning("Resultado descartado, 'document' no es un objeto: %r", jugador)
                continue
            jugadores.append(jugador)

        return jugadores

    async def _buscar_en_api(self, full_name: str, bearer_token: str) -> float | None:
        """
        Realiza la búsqueda en la API de la RFEG.

        El nombre se envía tal como lo escribió el jugador y se compara contra las
        respuestas ya normalizado a ambos lados: la federación no normaliza lo que
        guarda —hay fichas con tildes, sin ellas y en mayúsculas y minúsculas
        mezcladas—, así que no hay grafía de la que fiarse.

        Args:
            full_name: Nombre completo del jugador
            bearer_token: Token de autorización en formato "Bearer {token}"

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
        params = {"q": full_name}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.URL_API_HANDICAP,
                params=params,
                headers=api_headers,
                timeout=self._timeout,
            )
            response.raise_for_status()

            # Un 200 con cuerpo que no es JSON (una página de mantenimiento, por
            # ejemplo) significa que la federación no está respondiendo lo que dice
            # responder. Sin esto el error de parseo escapa del
            # `except httpx.HTTPError` de search_handicap y tumba el registro con un
            # 500, en vez de dejarlo seguir sin hándicap como promete su comentario.
            try:
                datos = response.json()
            except ValueError as e:
                raise HandicapServiceUnavailableError(
                    f"La RFEG devolvió una respuesta que no es JSON: {e}"
                ) from e

            # Buscar coincidencia exacta en todos los resultados
            # La API de RFEG devuelve la estructura: {"data": {"hits": [{"document": {...}}]}}
            #
            # La comparación se hace sobre el texto normalizado a ambos lados: la
            # federación guarda los nombres con sus tildes y el jugador puede
            # escribirlos sin ellas (o al revés). Comparar en literal hacía fallar
            # la búsqueda en cuanto las dos grafías no coincidían exactamente.
            nombre_buscado = self._normalizar_para_comparar(full_name).upper()

            for jugador in self._extraer_jugadores(datos):
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
                        # Un hándicap ilegible se descarta, pero con rastro: un
                        # cambio de formato al otro lado degradaría la búsqueda en
                        # silencio y no habría forma de saber por qué.
                        logger.warning(
                            "Hándicap no numérico en la respuesta de la RFEG para '%s': %r",
                            nombre_encontrado,
                            handicap,
                        )
                        continue

            return None
