"""
Tests unitarios para RFEGHandicapService

Verifica la funcionalidad de normalización de texto para eliminar acentos.
"""

import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

from src.modules.user.infrastructure.external.rfeg_handicap_service import (
    RFEGHandicapService,
)


class TestRFEGHandicapServiceNormalizacion:
    """Tests para la normalización de texto"""

    def test_normalizar_texto_con_acentos(self):
        """Debe eliminar acentos de caracteres españoles"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Agustín")

        # Assert
        assert resultado == "Agustin"

    def test_normalizar_texto_con_multiples_acentos(self):
        """Debe eliminar todos los acentos de un nombre completo"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("José María López García")

        # Assert
        assert resultado == "Jose Maria Lopez Garcia"

    def test_normalizar_texto_sin_acentos(self):
        """No debe modificar texto que ya no tiene acentos"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Juan Carlos Perez")

        # Assert
        assert resultado == "Juan Carlos Perez"

    def test_normalizar_texto_con_enie(self):
        """Debe normalizar la ñ a n (NFD descompone todos los diacríticos)"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Peña")

        # Assert
        assert resultado == "Pena"

    def test_normalizar_texto_vacio(self):
        """Debe manejar string vacío"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("")

        # Assert
        assert resultado == ""

    def test_normalizar_texto_con_dieresis(self):
        """Debe eliminar diéresis"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Güell")

        # Assert
        assert resultado == "Guell"

    def test_normalizar_texto_con_espacios_extra(self):
        """Debe eliminar espacios extra al principio, al final y entre palabras"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("  José   Buela  Fernández  ")

        # Assert
        assert resultado == "Jose Buela Fernandez"


class TestRFEGHandicapServiceBusqueda:
    """
    Tests de `search_handicap` de punta a punta, con la RFEG falseada.

    Cubren el hueco de la issue #268: la normalización estaba bien probada en el
    helper, pero el resultado se descartaba un paso después al comparar la
    respuesta en literal.
    """

    TOKEN_HTML = "var x = 'coded_" + "a1b2c3d4" * 4 + "';"

    @staticmethod
    def _respuesta_token():
        """Falsea la página principal de la que se extrae el token Bearer."""
        respuesta = MagicMock()
        respuesta.text = TestRFEGHandicapServiceBusqueda.TOKEN_HTML
        respuesta.raise_for_status = MagicMock()
        return respuesta

    @staticmethod
    def _respuesta_api(*jugadores: dict):
        """Falsea la respuesta de la API de búsqueda con los jugadores dados."""
        respuesta = MagicMock()
        respuesta.raise_for_status = MagicMock()
        respuesta.json = MagicMock(
            return_value={"data": {"hits": [{"document": j} for j in jugadores]}}
        )
        return respuesta

    @staticmethod
    def _cliente_que_devuelve(*respuestas):
        """Monta el AsyncClient falso que irá soltando `respuestas` en orden."""
        cliente = AsyncMock()
        cliente.get = AsyncMock(side_effect=list(respuestas))
        cliente.__aenter__ = AsyncMock(return_value=cliente)
        cliente.__aexit__ = AsyncMock(return_value=None)
        return cliente

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_encuentra_con_tildes_a_los_dos_lados(self, mock_client_class):
        """El jugador escribe su nombre con tildes y la RFEG lo guarda con tildes"""
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api({"full_name": "AGUSTÍN ESTÉVEZ", "handicap": 15.4}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Agustín Estévez")

        # Assert
        assert handicap == 15.4

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_encuentra_escribiendolo_sin_tildes(self, mock_client_class):
        """
        El jugador teclea su nombre sin tildes y la RFEG lo guarda con ellas.

        Este es el caso que la issue #268 da por roto: no había reintento, porque
        el nombre ya venía normalizado, y la única búsqueda comparaba en literal.
        """
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api({"full_name": "AGUSTÍN ESTÉVEZ", "handicap": 15.4}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Agustin Estevez")

        # Assert
        assert handicap == 15.4

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_encuentra_cuando_la_rfeg_responde_sin_tildes(self, mock_client_class):
        """El jugador escribe con tildes y la federación responde sin ellas"""
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api({"full_name": "AGUSTIN ESTEVEZ", "handicap": 15.4}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Agustín Estévez")

        # Assert
        assert handicap == 15.4

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_un_nombre_sin_tildes_sigue_funcionando(self, mock_client_class):
        """Sin tildes por ninguna parte, el comportamiento no cambia"""
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api({"full_name": "JUAN LOPEZ", "handicap": 24.0}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Juan Lopez")

        # Assert
        assert handicap == 24.0

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_no_casa_con_otro_jugador_de_los_resultados(self, mock_client_class):
        """
        Normalizar no puede aflojar la comparación más allá de los acentos.

        La búsqueda devuelve varios jugadores y ninguno es el buscado: el
        resultado debe seguir siendo None, no el hándicap del primero.
        """
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api(
                {"full_name": "AGUSTÍN ESTÉVEZ GARCÍA", "handicap": 8.0},
                {"full_name": "AGUSTÍN ESTÉBAN", "handicap": 12.0},
            ),
            self._respuesta_api(),  # el reintento sin tildes tampoco encuentra
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Agustín Estévez")

        # Assert
        assert handicap is None

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_un_resultado_sin_nombre_no_rompe_la_busqueda(self, mock_client_class):
        """Un hit con `full_name` nulo se ignora en vez de reventar la búsqueda"""
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api(
                {"full_name": None, "handicap": 3.0},
                {"full_name": "AGUSTÍN ESTÉVEZ", "handicap": 15.4},
            ),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Agustín Estévez")

        # Assert
        assert handicap == 15.4

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_reintenta_sin_tildes_cuando_la_primera_no_devuelve_nada(self, mock_client_class):
        """
        El reintento se mantiene: la RFEG puede devolver otros resultados para la
        consulta sin acentos, y esa es su razón de ser tras la issue #268.
        """
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api(),  # con tildes, la federación no devuelve nada
            self._respuesta_api({"full_name": "AGUSTÍN ESTÉVEZ", "handicap": 15.4}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Agustín Estévez")

        # Assert
        assert handicap == 15.4
        consultas = [
            llamada.kwargs["params"]["q"]
            for llamada in cliente.get.await_args_list
            if "params" in llamada.kwargs
        ]
        assert consultas == ["Agustín Estévez", "Agustin Estevez"]


class TestRFEGHandicapServiceComparacionConEnie:
    """
    La eñe se preserva al comparar respuestas, no al construir la consulta.

    `Peña` y `Pena` son dos apellidos distintos: casarlos escribiría el hándicap
    de otra persona, y sin confirmación humana en cuatro de los cinco flujos.
    """

    def test_conserva_la_enie_pero_quita_las_tildes(self):
        """Debe quitar tildes y dejar la eñe intacta"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_para_comparar("Ibáñez")

        # Assert
        assert resultado == "Ibañez"

    def test_distingue_pena_de_penia(self):
        """Los dos apellidos no pueden colapsar en el mismo texto"""
        # Arrange & Act
        con_enie = RFEGHandicapService._normalizar_para_comparar("Peña")
        sin_enie = RFEGHandicapService._normalizar_para_comparar("Pena")

        # Assert
        assert con_enie != sin_enie

    def test_reconoce_la_enie_ya_descompuesta(self):
        """
        Si la RFEG devuelve la eñe en NFD (n + tilde combinante) hay que
        componerla antes, o el borrado de diacríticos se la llevaría igual.
        """
        # Arrange
        enie_descompuesta = unicodedata.normalize("NFD", "Peña")

        # Act
        resultado = RFEGHandicapService._normalizar_para_comparar(enie_descompuesta)

        # Assert
        assert resultado == "Peña"

    def test_la_consulta_sigue_quitando_la_enie(self):
        """`_normalizar_texto` no cambia: para buscar, la eñe se sigue quitando"""
        # Arrange & Act
        resultado = RFEGHandicapService._normalizar_texto("Peña")

        # Assert
        assert resultado == "Pena"


class TestRFEGHandicapServiceBusquedaCasosLimite:
    """Casos límite de `search_handicap` salidos de la revisión de la #268"""

    _respuesta_token = staticmethod(TestRFEGHandicapServiceBusqueda._respuesta_token)
    _respuesta_api = staticmethod(TestRFEGHandicapServiceBusqueda._respuesta_api)
    _cliente_que_devuelve = staticmethod(TestRFEGHandicapServiceBusqueda._cliente_que_devuelve)

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_no_casa_pena_con_penia(self, mock_client_class):
        """Un `Pena` no puede llevarse el hándicap de un `Peña`"""
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api({"full_name": "JUAN PEÑA GARCIA", "handicap": 8.0}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Juan Pena Garcia")

        # Assert
        assert handicap is None

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_no_casa_penia_con_pena(self, mock_client_class):
        """Y al revés: un `Peña` tampoco se lleva el de un `Pena`"""
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api({"full_name": "JUAN PENA GARCIA", "handicap": 8.0}),
            self._respuesta_api({"full_name": "JUAN PENA GARCIA", "handicap": 8.0}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Juan Peña García")

        # Assert
        assert handicap is None

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_encuentra_a_un_penia_de_verdad(self, mock_client_class):
        """Preservar la eñe no puede impedir encontrar a quien sí la lleva"""
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api({"full_name": "JUAN PEÑA GARCÍA", "handicap": 8.0}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Juan Peña Garcia")

        # Assert
        assert handicap == 8.0

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_un_handicap_no_numerico_no_provoca_un_500(self, mock_client_class):
        """
        Un hándicap ilegible debe quedarse en "no encontrado".

        `float("N/A")` lanza ValueError, que no captura el `except httpx.HTTPError`
        de `search_handicap`: escaparía del caso de uso como un 500.
        """
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api({"full_name": "AGUSTÍN ESTÉVEZ", "handicap": "N/A"}),
            self._respuesta_api({"full_name": "AGUSTÍN ESTÉVEZ", "handicap": "N/A"}),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Agustín Estévez")

        # Assert
        assert handicap is None

    @patch("src.modules.user.infrastructure.external.rfeg_handicap_service.httpx.AsyncClient")
    async def test_sigue_buscando_tras_un_handicap_ilegible(self, mock_client_class):
        """Un hit con hándicap ilegible no puede tapar al siguiente que sí vale"""
        # Arrange
        cliente = self._cliente_que_devuelve(
            self._respuesta_token(),
            self._respuesta_api(
                {"full_name": "AGUSTÍN ESTÉVEZ", "handicap": "15,4"},
                {"full_name": "AGUSTÍN ESTÉVEZ", "handicap": 15.4},
            ),
        )
        mock_client_class.return_value = cliente

        # Act
        handicap = await RFEGHandicapService().search_handicap("Agustín Estévez")

        # Assert
        assert handicap == 15.4
