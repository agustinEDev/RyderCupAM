"""
RFEG Handicap Service - Infrastructure Layer

Implementación concreta del servicio de hándicap usando la API de la RFEG.
Adaptador que encapsula la lógica de scraping del sistema de hándicaps de la
Real Federación Española de Golf.
"""

import re
import unicodedata
import httpx
from typing import Optional

from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.errors.handicap_errors import (
    HandicapServiceUnavailableError
)


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

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/26.0.1 Safari/605.1.15"
        ),
        "Origin": "https://rfegolf.es",
        "Referer": "https://rfegolf.es/"
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
        texto_limpio = re.sub(r'\s+', ' ', texto_limpio)

        # 3. NFD descompone caracteres acentuados en base + acento
        #    Luego filtramos los caracteres de categoría Mn (Nonspacing_Mark)
        nfd = unicodedata.normalize('NFD', texto_limpio)
        return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

    async def search_handicap(self, full_name: str) -> Optional[float]:
        """
        Busca el hándicap de un jugador en la RFEG.

        Intenta primero con el nombre original y si no encuentra resultados,
        reintenta con el nombre normalizado (sin acentos).

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

            # 3. Si no se encontró, reintentar con nombre normalizado (sin acentos)
            nombre_normalizado = self._normalizar_texto(full_name)
            if nombre_normalizado != full_name:
                return await self._buscar_en_api(nombre_normalizado, bearer_token)

            return None

        except httpx.HTTPError as e:
            raise HandicapServiceUnavailableError(
                f"Error de conexión con el servicio RFEG: {e}"
            )

    async def _obtener_bearer_token(self) -> Optional[str]:
        """
        Obtiene el token Bearer extrayéndolo de la página principal.

        El token se encuentra en el código JavaScript de la página
        y tiene el formato 'coded_[hexadecimal]'.

        Returns:
            Token en formato "Bearer {token}" o None si no se encuentra
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.URL_PAGINA_PRINCIPAL,
                headers=self.HEADERS,
                timeout=self._timeout
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
        self,
        full_name: str,
        bearer_token: str
    ) -> Optional[float]:
        """
        Realiza la búsqueda en la API de la RFEG.

        Args:
            full_name: Nombre completo del jugador
            bearer_token: Token de autorización en formato "Bearer {token}"

        Returns:
            Hándicap del primer resultado encontrado o None
        """
        # Preparar headers con el token de autorización
        api_headers = self.HEADERS.copy()
        api_headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Authorization": bearer_token
        })

        # Parámetros de búsqueda
        params = {'q': full_name}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.URL_API_HANDICAP,
                params=params,
                headers=api_headers,
                timeout=self._timeout
            )
            response.raise_for_status()

            datos = response.json()

            # Buscar coincidencia exacta en todos los resultados
            # La API de RFEG devuelve la estructura: {"data": {"hits": [{"document": {...}}]}}
            if datos and 'data' in datos:
                hits = datos['data'].get('hits') or []
                nombre_buscado = full_name.upper()

                for hit in hits:
                    jugador = (hit or {}).get('document', {})
                    nombre_encontrado = jugador.get('full_name', '').upper()

                    if nombre_encontrado == nombre_buscado:
                        handicap = jugador.get('handicap')
                        if handicap is not None:
                            return float(handicap)

            return None
