"""
Tests E2E para Competition Endpoints.

Tests de integración que verifican el flujo completo de los endpoints
de competiciones incluyendo autenticación, validaciones y persistencia.
"""

import uuid
from datetime import date, datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    activate_competition,
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_draft_competition,
    create_golf_course,
    estado_en_bd,
    set_auth_cookies,
)


class TestCreateCompetition:
    """Tests para POST /api/v1/competitions"""

    @pytest.mark.asyncio
    async def test_create_competition_success(self, client: AsyncClient):
        """Crear competición exitosamente retorna 201."""
        # Arrange
        user = await create_authenticated_user(
            client, "creator@test.com", "P@ssw0rd123!", "Creator", "Test"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        competition_data = {
            "name": "Ryder Cup Integration Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        # Act
        response = await client.post(
            "/api/v1/competitions", json=competition_data, cookies=user["cookies"]
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Ryder Cup Integration Test"
        assert data["status"] == "ACTIVE"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_competition_without_auth_returns_401(self, client: AsyncClient):
        """Crear competición sin autenticación retorna 401."""
        competition_data = {
            "name": "Test",
            "start_date": "2025-12-01",
            "end_date": "2025-12-03",
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        response = await client.post("/api/v1/competitions", json=competition_data)
        # Con HTTPOnly Cookies, retorna 401 cuando no hay autenticación
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_competition_invalid_dates_returns_400(self, client: AsyncClient):
        """Crear competición con fechas inválidas retorna 400."""
        user = await create_authenticated_user(
            client, "creator2@test.com", "P@ssw0rd123!", "Creator", "Two"
        )

        # end_date antes de start_date
        competition_data = {
            "name": "Invalid Dates Test",
            "start_date": "2025-12-10",
            "end_date": "2025-12-05",
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        response = await client.post(
            "/api/v1/competitions", json=competition_data, cookies=user["cookies"]
        )

        assert response.status_code == 422  # Validation error


class TestListCompetitions:
    """Tests para GET /api/v1/competitions"""

    @pytest.mark.asyncio
    async def test_list_competitions_empty(self, client: AsyncClient):
        """Listar competiciones vacío retorna lista vacía."""
        user = await create_authenticated_user(
            client, "lister@test.com", "P@ssw0rd123!", "List", "User"
        )

        response = await client.get("/api/v1/competitions", cookies=user["cookies"])

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_competitions_with_data(self, client: AsyncClient):
        """Listar competiciones retorna las creadas."""
        user = await create_authenticated_user(
            client, "lister2@test.com", "P@ssw0rd123!", "List", "Two"
        )

        # Crear 2 competiciones
        await create_competition(client, user["cookies"])

        start = date.today() + timedelta(days=60)
        end = start + timedelta(days=3)
        comp2_data = {
            "name": "Second Competition",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "FR",
            "play_mode": "SCRATCH",
            "max_players": 16,
            "team_assignment": "MANUAL",
        }
        await create_competition(client, user["cookies"], comp2_data)

        # Act
        response = await client.get("/api/v1/competitions", cookies=user["cookies"])

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_competitions_filter_by_status(self, client: AsyncClient):
        """Filtrar competiciones por estado."""
        user = await create_authenticated_user(
            client, "filterer@test.com", "P@ssw0rd123!", "Filter", "User"
        )

        # Crear y activar una competición
        comp = await create_competition(client, user["cookies"])
        await activate_competition(client, user["cookies"], comp["id"])

        # Crear otra que siga en DRAFT: desde BE #332 la unica que espera es
        # la que tiene apertura programada
        start = date.today() + timedelta(days=90)
        end = start + timedelta(days=3)
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Draft Competition",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
                "enrollment_opens_days_before": 5,
            },
        )

        # Filtrar solo ACTIVE
        response = await client.get("/api/v1/competitions?status=ACTIVE", cookies=user["cookies"])

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_list_competitions_filter_by_creator_alias(self, client: AsyncClient):
        """
        Buscar por el creador encuentra también por su alias (BE #239).

        Quien organiza aparece por su apodo en el resto de la aplicación, así
        que buscarlo por el nombre que se ve en pantalla tiene que funcionar.
        """
        user = await create_authenticated_user(
            client, "organizador@test.com", "P@ssw0rd123!", "Agustin", "Estevez"
        )
        await client.patch(
            "/api/v1/users/profile",
            json={"alias": "Chuchi"},
            cookies=user["cookies"],
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)
        # El nombre se guarda normalizado —«del» sale como «Del»—, así que lo
        # que se espera sale de la respuesta y no del literal que se envía
        creada = await create_competition(
            client,
            user["cookies"],
            {
                "name": "Torneo del Chuchi",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )

        # Una segunda competición de OTRO creador con OTRO alias. Sin ella el
        # test pasaría aunque la búsqueda devolviera todo, que es justo el
        # fallo que puede tener esta rama
        otro = await create_authenticated_user(
            client, "otroorganizador@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )
        await client.patch(
            "/api/v1/users/profile",
            json={"alias": "Anita"},
            cookies=otro["cookies"],
        )
        await create_competition(
            client,
            otro["cookies"],
            {
                "name": "Torneo de Anita",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )

        response = await client.get(
            "/api/v1/competitions?search_creator=Chuchi", cookies=user["cookies"]
        )

        assert response.status_code == 200
        data = response.json()
        assert [c["name"] for c in data] == [creada["name"]]

    async def test_list_competitions_by_creator_ignores_a_blank_search(
        self, client: AsyncClient
    ):
        """
        Buscar por espacios no devuelve la lista entera.

        `LOWER(alias) LIKE '%%'` casa con cualquier alias, así que recortar el
        texto antes de buscarlo convertía «  » en «devuélvemelo todo». El texto
        va tal cual, y dos espacios no casan con nada.
        """
        user = await create_authenticated_user(
            client, "blanco@test.com", "P@ssw0rd123!", "Agustin", "Estevez"
        )
        await client.patch(
            "/api/v1/users/profile",
            json={"alias": "Chuchi"},
            cookies=user["cookies"],
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Torneo que no debe salir",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )

        response = await client.get(
            "/api/v1/competitions?search_creator=%20%20", cookies=user["cookies"]
        )

        assert response.status_code == 200
        assert response.json() == []

    async def test_list_competitions_by_creator_does_not_treat_a_percent_as_a_wildcard(
        self, client: AsyncClient
    ):
        """
        Un `%` tecleado se busca como carácter, no como comodín.

        Interpolando el texto dentro del patrón —`ILIKE f"%{x}%"`— buscar `%`
        devolvía todas las competiciones.
        """
        user = await create_authenticated_user(
            client, "comodin@test.com", "P@ssw0rd123!", "Agustin", "Estevez"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Torneo tampoco visible",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )

        response = await client.get(
            "/api/v1/competitions?search_creator=%25", cookies=user["cookies"]
        )

        assert response.status_code == 200
        assert response.json() == []

    async def test_list_competitions_by_creator_still_finds_a_real_name(
        self, client: AsyncClient
    ):
        """
        La rama nueva del OR no puede tapar la búsqueda de siempre.

        Quien no tiene alias —LOWER(NULL)— tiene que seguir apareciendo al
        buscarlo por su nombre real.
        """
        user = await create_authenticated_user(
            client, "sinapodo@test.com", "P@ssw0rd123!", "Ana", "Garcia"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)
        creada = await create_competition(
            client,
            user["cookies"],
            {
                "name": "Torneo de Ana",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )

        response = await client.get(
            "/api/v1/competitions?search_creator=Garcia", cookies=user["cookies"]
        )

        assert response.status_code == 200
        data = response.json()
        assert [c["name"] for c in data] == [creada["name"]]

    async def test_list_competitions_filter_by_search_name(self, client: AsyncClient):
        """Filtrar competiciones por nombre de búsqueda."""
        user = await create_authenticated_user(
            client, "searcher@test.com", "P@ssw0rd123!", "Search", "User"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        # Crear competiciones
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Ryder Cup 2025",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Open de España",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )
        await create_competition(
            client,
            user["cookies"],
            {
                "name": "Ryder Cup Friends",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "max_players": 24,
                "team_assignment": "MANUAL",
            },
        )

        # Filtrar por "Ryder"
        response = await client.get(
            "/api/v1/competitions?search_name=Ryder", cookies=user["cookies"]
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert "Ryder Cup 2025" in [c["name"] for c in data]
        assert "Ryder Cup Friends" in [c["name"] for c in data]


class TestMyCompetitionsFilter:
    """Tests para el filtro `my_competitions` en GET /api/v1/competitions"""

    @pytest.mark.asyncio
    async def test_list_my_competitions_as_creator(self, client: AsyncClient):
        """`my_competitions=true` devuelve solo las competiciones creadas por el usuario."""
        creator = await create_authenticated_user(
            client, "my_creator@test.com", "P@ssw0rd123!", "My", "Creator"
        )
        other_user = await create_authenticated_user(
            client, "other_creator@test.com", "P@ssw0rd123!", "Other", "Creator"
        )

        # Crear competiciones
        await create_competition(client, creator["cookies"])  # Creada por el usuario
        await create_competition(client, other_user["cookies"])  # Creada por otro

        # Act
        response = await client.get(
            "/api/v1/competitions?my_competitions=true", cookies=creator["cookies"]
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["creator_id"] == creator["user"]["id"]

    @pytest.mark.asyncio
    async def test_list_my_competitions_as_enrolled(self, client: AsyncClient):
        """`my_competitions=true` devuelve competiciones en las que el usuario está inscrito."""
        creator = await create_authenticated_user(
            client, "enrolled_creator@test.com", "P@ssw0rd123!", "Enrolled", "Creator"
        )
        enrolled_user = await create_authenticated_user(
            client, "enrolled_user@test.com", "P@ssw0rd123!", "Enrolled", "User"
        )

        # Crear competición y activar
        comp = await create_competition(client, creator["cookies"])
        await activate_competition(client, creator["cookies"], comp["id"])

        # Inscribir usuario
        await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments",
            cookies=enrolled_user["cookies"],
        )

        # Act
        response = await client.get(
            "/api/v1/competitions?my_competitions=true",
            cookies=enrolled_user["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == comp["id"]


class TestGetCompetition:
    """Tests para GET /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_get_competition_success(self, client: AsyncClient):
        """Obtener competición por ID retorna datos completos, incluyendo el creador."""
        user = await create_authenticated_user(
            client, "getter@test.com", "P@ssw0rd123!", "Get", "User"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.get(f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"])

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == comp["id"]
        assert "is_creator" in data
        assert data["is_creator"] is True
        assert "creator" in data
        assert data["creator"]["id"] == user["user"]["id"]
        assert data["creator"]["first_name"] == "Get"
        assert data["creator"]["last_name"] == "User"

    @pytest.mark.asyncio
    async def test_get_competition_not_found(self, client: AsyncClient):
        """Obtener competición inexistente retorna 404."""
        user = await create_authenticated_user(
            client, "getter2@test.com", "P@ssw0rd123!", "Get", "Two"
        )

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/v1/competitions/{fake_id}", cookies=user["cookies"])

        assert response.status_code == 404


class TestUpdateCompetition:
    """Tests para PUT /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_update_competition_success(self, client: AsyncClient):
        """Actualizar competición en DRAFT exitosamente."""
        user = await create_authenticated_user(
            client, "updater@test.com", "P@ssw0rd123!", "Update", "User"
        )

        comp = await create_competition(client, user["cookies"])

        update_data = {
            "name": "Updated Ryder Cup Name",
            "max_players": 50,
            "team_assignment": "AUTOMATIC",
            "team_1_name": "Team Europe Updated",
        }

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json=update_data,
            cookies=user["cookies"],
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Ryder Cup Name"
        assert data["max_players"] == 50
        assert data["team_assignment"] == "AUTOMATIC"
        # team_1_name no está en el response DTO, así que no podemos verificarlo directamente
        # Para verificarlo, necesitaríamos un GET y que el DTO de GET lo incluyera.
        # Por ahora, confiamos en que el cambio se aplicó si el resto funciona.

    @pytest.mark.asyncio
    async def test_update_competition_applies_the_cap_sent_as_number_of_players(
        self, client: AsyncClient
    ):
        """El cupo debe cambiar cuando llega como `number_of_players`.

        Es el nombre que manda el cliente web en las dos llamadas. Sin el alias en
        el DTO de actualización, Pydantic descartaba la clave, el cupo se quedaba
        como estaba y la respuesta seguía siendo un 200: nada llegaba al usuario.
        """
        user = await create_authenticated_user(
            client, "capupdater@test.com", "P@ssw0rd123!", "Cap", "Updater"
        )

        comp = await create_competition(client, user["cookies"])
        assert comp["max_players"] == 24

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"number_of_players": 20},
            cookies=user["cookies"],
        )

        assert response.status_code == 200

        despues = await client.get(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )
        assert despues.status_code == 200
        assert despues.json()["max_players"] == 20

    @pytest.mark.asyncio
    async def test_update_competition_rejects_a_cap_above_the_limit(self, client: AsyncClient):
        """Un cupo por encima de 100 debe dar 422, no un 200 silencioso."""
        user = await create_authenticated_user(
            client, "capmax@test.com", "P@ssw0rd123!", "Cap", "Max"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"number_of_players": 101},
            cookies=user["cookies"],
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_competition_accepts_the_maximum_cap(self, client: AsyncClient):
        """100 jugadores: el cupo máximo debe entrar."""
        user = await create_authenticated_user(
            client, "capmaximo@test.com", "P@ssw0rd123!", "Cap", "Maximo"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"number_of_players": 100},
            cookies=user["cookies"],
        )

        assert response.status_code == 200

        despues = await client.get(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )
        assert despues.json()["max_players"] == 100

    @pytest.mark.asyncio
    async def test_update_competition_applies_the_countries_sent_by_the_client(
        self, client: AsyncClient
    ):
        """Los países acompañantes deben cambiar cuando llegan como `countries`.

        Mismo hueco que el del cupo: la pantalla manda el mismo payload para crear
        y para editar, y al editar el backend lo descartaba sin decir nada.
        """
        user = await create_authenticated_user(
            client, "countriesupdater@test.com", "P@ssw0rd123!", "Countries", "Updater"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"main_country": "ES", "countries": ["PT"]},
            cookies=user["cookies"],
        )

        assert response.status_code == 200

        despues = await client.get(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )
        codigos = [c["code"] for c in despues.json()["countries"]]
        assert "PT" in codigos

    @pytest.mark.asyncio
    async def test_update_competition_normalises_a_lowercase_country_code(
        self, client: AsyncClient
    ):
        """Un código en minúscula debe acabar guardado como ISO, en mayúsculas.

        Quien normaliza es `CountryCode`, no el DTO: esto lo comprueba de punta a
        punta para que la pieza que lo haga pueda cambiar sin que nadie lo note.
        """
        user = await create_authenticated_user(
            client, "lowercountry@test.com", "P@ssw0rd123!", "Lower", "Country"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"countries": ["pt"]},
            cookies=user["cookies"],
        )

        assert response.status_code == 200

        despues = await client.get(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )
        codigos = [c["code"] for c in despues.json()["countries"]]
        assert "PT" in codigos

    @pytest.mark.asyncio
    async def test_update_competition_with_a_non_adjacent_country_returns_400(
        self, client: AsyncClient
    ):
        """Un país que no vale debe dar 400 al editar, igual que al crear.

        El `except` del PUT no contemplaba InvalidCountryError, que hasta ahora no
        podía llegar porque `countries` se descartaba antes.
        """
        user = await create_authenticated_user(
            client, "badcountry@test.com", "P@ssw0rd123!", "Bad", "Country"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"countries": ["JP"]},
            cookies=user["cookies"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_competition_with_a_malformed_country_code_returns_400(
        self, client: AsyncClient
    ):
        """Un código de dos caracteres pero mal formado debe dar 400, no 500.

        Pasa la validación del DTO, que solo mira la longitud, y revienta al
        construir el CountryCode con un error que no hereda de ValueError.
        """
        user = await create_authenticated_user(
            client, "malformed@test.com", "P@ssw0rd123!", "Mal", "Formed"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"countries": ["1a"]},
            cookies=user["cookies"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_competition_tolerates_padding_in_a_country_code(
        self, client: AsyncClient
    ):
        """Un código con espacios debe valer, como en los campos hermanos."""
        user = await create_authenticated_user(
            client, "padded@test.com", "P@ssw0rd123!", "Pad", "Ded"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"countries": ["PT "]},
            cookies=user["cookies"],
        )

        assert response.status_code == 200

        despues = await client.get(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )
        assert "PT" in [c["code"] for c in despues.json()["countries"]]

    @pytest.mark.asyncio
    async def test_update_competition_with_a_repeated_country_returns_400(
        self, client: AsyncClient
    ):
        """Repetir un país acompañante debe dar 400, no 500.

        `Location` lo rechaza con `InvalidLocationError`, que tampoco hereda de
        `ValueError`: la tercera cara del mismo defecto en esta rama.
        """
        user = await create_authenticated_user(
            client, "repeatedcountry@test.com", "P@ssw0rd123!", "Repeated", "Country"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"main_country": "ES", "countries": ["PT", "PT"]},
            cookies=user["cookies"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_competition_not_creator_returns_403(self, client: AsyncClient):
        """Actualizar competición de otro usuario retorna 403."""
        creator = await create_authenticated_user(
            client, "creator3@test.com", "P@ssw0rd123!", "Creator", "Three"
        )
        other_user = await create_authenticated_user(
            client, "other@test.com", "P@ssw0rd123!", "Other", "User"
        )

        comp = await create_competition(client, creator["cookies"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"name": "Hacked Name"},
            cookies=other_user["cookies"],
        )

        assert response.status_code == 403


class TestDeleteCompetition:
    """Tests para DELETE /api/v1/competitions/{id}"""

    @pytest.mark.asyncio
    async def test_delete_competition_success(self, client: AsyncClient):
        """Eliminar competición en DRAFT retorna 204."""
        user = await create_authenticated_user(
            client, "deleter@test.com", "P@ssw0rd123!", "Delete", "User"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_active_competition_succeeds(self, client: AsyncClient):
        """BE #333: con las inscripciones abiertas todavía se puede borrar.

        Las competiciones nacen abiertas (BE #332), así que dejar el borrado solo
        en DRAFT dejaba cancelar como única salida a un error al crearlas.
        """
        user = await create_authenticated_user(
            client, "deleter2@test.com", "P@ssw0rd123!", "Delete", "Two"
        )

        jugador = await create_authenticated_user(
            client, "enrolled@test.com", "P@ssw0rd123!", "Enrolled", "Player"
        )

        comp = await create_competition(client, user["cookies"])
        await activate_competition(client, user["cookies"], comp["id"])

        # Con alguien dentro: si la cascada no llegara a las inscripciones, el
        # borrado reventaria contra la clave ajena en vez de responder 204
        client.cookies.clear()
        client.cookies.update(user["cookies"])
        inscrito = await client.post(
            f"/api/v1/competitions/{comp['id']}/enrollments/direct",
            json={"competition_id": comp["id"], "user_id": jugador["user"]["id"]},
        )
        assert inscrito.status_code == 201, inscrito.text

        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )

        assert response.status_code == 204

        # Y deja de existir de verdad, no solo responde que sí
        client.cookies.clear()
        client.cookies.update(user["cookies"])
        assert (await client.get(f"/api/v1/competitions/{comp['id']}")).status_code == 404

    @pytest.mark.asyncio
    async def test_delete_closed_competition_returns_400(self, client: AsyncClient):
        """BE #333: cerradas las inscripciones ya no se borra.

        A partir de aquí se sortean equipos y se generan partidos, y el borrado
        va en cascada hasta los golpes anotados.
        """
        user = await create_authenticated_user(
            client, "deleter3@test.com", "P@ssw0rd123!", "Delete", "Three"
        )

        comp = await create_competition(client, user["cookies"])
        await activate_competition(client, user["cookies"], comp["id"])

        client.cookies.clear()
        client.cookies.update(user["cookies"])
        cerrada = await client.post(f"/api/v1/competitions/{comp['id']}/close-enrollments")
        assert cerrada.status_code == 200, cerrada.text

        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )

        assert response.status_code == 400
        assert "CLOSED" in response.json()["detail"]


class TestListingOpensScheduledCompetitions:
    """BE #331: verla en un listado tambien la abre, no solo abrir su ficha."""

    @pytest.mark.asyncio
    async def test_listing_opens_a_scheduled_competition_whose_day_has_passed(
        self, client: AsyncClient
    ):
        """Por HTTP, que es donde se murio esto la vez anterior.

        En BE #327 la apertura funcionaba en 31 tests unitarios y no ocurria
        jamas en produccion, porque ninguna ruta pasaba por el caso de uso. Este
        test existe para que el listado no pueda quedarse asi.
        """
        admin = await create_admin_user(
            client, "listado_admin@test.com", "AdminP@ssw0rd123!", "Listado", "Admin"
        )
        user = await create_authenticated_user(
            client, "listado_club@test.com", "P@ssw0rd123!", "Listado", "Club"
        )

        # Empieza en 3 dias y abre 5 antes: su momento ya paso
        empieza = date.today() + timedelta(days=3)
        comp = await create_competition(
            client,
            user["cookies"],
            {
                "name": f"Publica programada {uuid.uuid4().hex[:8]}",
                "start_date": empieza.isoformat(),
                "end_date": (empieza + timedelta(days=2)).isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "visibility": "PUBLIC",
                "enrollment_opens_days_before": 5,
            },
        )
        assert comp["status"] == "DRAFT"

        # La zona sale de las coordenadas del campo, no del pais (BE #305)
        golf_course = await create_golf_course(
            client,
            user["cookies"],
            golf_course_data={
                "name": f"Campo con zona {uuid.uuid4().hex[:8]}",
                "country_code": "ES",
                "course_type": "STANDARD_18",
                # Las coordenadas van DENTRO de location: sueltas se ignoran, el
                # campo se crea sin zona y la competicion no abre nunca (BE #327)
                "location": {"latitude": 40.4168, "longitude": -3.7038},
                "tees": [
                    {
                        "identifier": "Blanco",
                        "color": "WHITE",
                        "tee_gender": "MALE",
                        "course_rating": 72.5,
                        "slope_rating": 135,
                        "par": 72,
                    },
                ],
                "holes": [
                    {"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)
                ],
            },
        )
        await approve_golf_course(client, admin["cookies"], golf_course["id"])
        set_auth_cookies(client, user["cookies"])
        asociado = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
        )
        assert asociado.status_code == 201, asociado.text

        # Sin abrir su ficha en ningun momento: solo el listado. Y se comprueba
        # contra la FILA GUARDADA, no con otra peticion: cualquier ruta que lea
        # la competicion la abriria ella misma, asi que el test pasaria aunque
        # el listado no hubiera hecho nada —o la hubiera abierto sin persistir,
        # que es el fallo que de verdad hay que cazar
        listado = await client.get("/api/v1/competitions", params={"status": "DRAFT"})
        assert listado.status_code == 200
        assert comp["id"] not in [c["id"] for c in listado.json()], (
            "una vez abierta ya no es un borrador, asi que no puede salir "
            "dentro de un listado filtrado por DRAFT"
        )

        guardado = await estado_en_bd(comp["id"])
        assert guardado == "ACTIVE", (
            "el listado tenia que haberla abierto y PERSISTIDO: en memoria no basta, "
            f"la siguiente peticion la encontraria en borrador otra vez. Estado: {guardado}"
        )


class TestDeleteReopenedCompetition:
    """BE #333: volver a ACTIVE no vuelve a hacer borrable un torneo montado."""

    @pytest.mark.asyncio
    async def test_delete_reopened_competition_with_rounds_returns_400(
        self, client: AsyncClient
    ):
        """Con calendario montado no se borra, aunque el estado haya vuelto a ACTIVE.

        El estado se puede andar hacia atrás y ninguna de esas vueltas deshace
        rondas ni partidos. Mirando solo el estado, la cascada se llevaría el
        torneo entero con sus tarjetas.
        """
        admin = await create_admin_user(
            client, "reopen-admin@test.com", "P@ssw0rd123!", "Reopen", "Admin"
        )
        user = await create_authenticated_user(
            client, "reopener@test.com", "P@ssw0rd123!", "Re", "Opener"
        )

        comp = await create_competition(client, user["cookies"])

        gc = await create_golf_course(client, user["cookies"])
        await approve_golf_course(client, admin["cookies"], gc["id"])

        set_auth_cookies(client, user["cookies"])
        asociado = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc["id"]},
        )
        assert asociado.status_code == 201, asociado.text

        await activate_competition(client, user["cookies"], comp["id"])

        set_auth_cookies(client, user["cookies"])
        cerrada = await client.post(f"/api/v1/competitions/{comp['id']}/close-enrollments")
        assert cerrada.status_code == 200, cerrada.text

        ronda = await client.post(
            f"/api/v1/competitions/{comp['id']}/rounds",
            json={
                "golf_course_id": gc["id"],
                "round_date": comp["start_date"],
                "session_type": "MORNING",
                "match_format": "SINGLES",
            },
        )
        assert ronda.status_code == 201, ronda.text

        reabierta = await client.post(
            f"/api/v1/competitions/{comp['id']}/reopen-enrollments"
        )
        assert reabierta.status_code == 200, reabierta.text
        assert reabierta.json()["status"] == "ACTIVE"

        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}", cookies=user["cookies"]
        )

        assert response.status_code == 400
        assert "calendario" in response.json()["detail"].lower()


class TestCompetitionStateTransitions:
    """Tests para transiciones de estado de Competition"""

    @pytest.mark.asyncio
    async def test_activate_competition(self, client: AsyncClient):
        """Activar competición cambia estado a ACTIVE."""
        user = await create_authenticated_user(
            client, "activator@test.com", "P@ssw0rd123!", "Activate", "User"
        )

        comp = await create_draft_competition(client, user["cookies"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate", cookies=user["cookies"]
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_cancel_competition(self, client: AsyncClient):
        """Cancelar competición cambia estado a CANCELLED."""
        user = await create_authenticated_user(
            client, "canceler@test.com", "P@ssw0rd123!", "Cancel", "User"
        )

        comp = await create_competition(client, user["cookies"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/cancel", cookies=user["cookies"]
        )

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, client: AsyncClient):
        """Test del ciclo de vida completo: DRAFT -> ACTIVE -> CLOSED -> IN_PROGRESS -> COMPLETED."""
        user = await create_authenticated_user(
            client, "lifecycle@test.com", "P@ssw0rd123!", "Life", "Cycle"
        )

        # 1. Crear (DRAFT)
        comp = await create_draft_competition(client, user["cookies"])
        assert comp["status"] == "DRAFT"

        # 2. Activar (ACTIVE)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate", cookies=user["cookies"]
        )
        assert response.json()["status"] == "ACTIVE"

        # 3. Cerrar inscripciones (CLOSED)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=user["cookies"],
        )
        assert response.json()["status"] == "CLOSED"

        # 4. Iniciar (IN_PROGRESS)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/start", cookies=user["cookies"]
        )
        assert response.json()["status"] == "IN_PROGRESS"

        # 5. Completar (COMPLETED)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/complete", cookies=user["cookies"]
        )
        assert response.json()["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_invalid_state_transition_returns_400(self, client: AsyncClient):
        """Transición de estado inválida retorna 400."""
        user = await create_authenticated_user(
            client, "invalid_trans@test.com", "P@ssw0rd123!", "Invalid", "Trans"
        )

        comp = await create_draft_competition(client, user["cookies"])

        # Intentar cerrar inscripciones desde DRAFT (debe ser ACTIVE)
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=user["cookies"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_revert_status_in_progress_to_closed(self, client: AsyncClient):
        """Revertir competición de IN_PROGRESS a CLOSED retorna 200."""
        user = await create_authenticated_user(
            client, "revert_status@test.com", "P@ssw0rd123!", "Revert", "Status"
        )

        comp = await create_draft_competition(client, user["cookies"])

        # Avanzar a IN_PROGRESS
        r1 = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate", cookies=user["cookies"]
        )
        assert r1.status_code == 200
        r2 = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=user["cookies"],
        )
        assert r2.status_code == 200
        r3 = await client.post(f"/api/v1/competitions/{comp['id']}/start", cookies=user["cookies"])
        assert r3.status_code == 200

        # Revertir a CLOSED
        response = await client.put(
            f"/api/v1/competitions/{comp['id']}/revert-status",
            cookies=user["cookies"],
        )

        assert response.status_code == 200
        assert response.json()["status"] == "CLOSED"

    @pytest.mark.asyncio
    async def test_reopen_enrollments_closed_to_active(self, client: AsyncClient):
        """Reabrir inscripciones de CLOSED a ACTIVE retorna 200."""
        user = await create_authenticated_user(
            client, "reopen_enroll@test.com", "P@ssw0rd123!", "Reopen", "Enroll"
        )

        comp = await create_draft_competition(client, user["cookies"])

        # Avanzar a CLOSED
        r1 = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate", cookies=user["cookies"]
        )
        assert r1.status_code == 200
        r2 = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=user["cookies"],
        )
        assert r2.status_code == 200

        # Reabrir inscripciones
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/reopen-enrollments",
            cookies=user["cookies"],
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_revert_status_from_wrong_state_returns_400(self, client: AsyncClient):
        """Revertir desde estado que no es IN_PROGRESS retorna 400."""
        user = await create_authenticated_user(
            client, "revert_wrong@test.com", "P@ssw0rd123!", "Revert", "Wrong"
        )

        comp = await create_competition(client, user["cookies"])

        # Competición está en DRAFT — no se puede revertir
        response = await client.put(
            f"/api/v1/competitions/{comp['id']}/revert-status",
            cookies=user["cookies"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_revert_to_in_progress_from_completed(self, client: AsyncClient):
        """Revertir competición de COMPLETED a IN_PROGRESS retorna 200."""
        user = await create_authenticated_user(
            client, "revert_to_ip@test.com", "P@ssw0rd123!", "Revert", "ToInProgress"
        )

        comp = await create_draft_competition(client, user["cookies"])

        # Avanzar a COMPLETED
        r1 = await client.post(
            f"/api/v1/competitions/{comp['id']}/activate", cookies=user["cookies"]
        )
        assert r1.status_code == 200
        r2 = await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=user["cookies"],
        )
        assert r2.status_code == 200
        r3 = await client.post(f"/api/v1/competitions/{comp['id']}/start", cookies=user["cookies"])
        assert r3.status_code == 200
        r4 = await client.post(
            f"/api/v1/competitions/{comp['id']}/complete", cookies=user["cookies"]
        )
        assert r4.status_code == 200

        # Revertir a IN_PROGRESS
        response = await client.put(
            f"/api/v1/competitions/{comp['id']}/revert-to-in-progress",
            cookies=user["cookies"],
        )

        assert response.status_code == 200
        assert response.json()["status"] == "IN_PROGRESS"

    @pytest.mark.asyncio
    async def test_revert_to_in_progress_from_wrong_state_returns_400(self, client: AsyncClient):
        """Revertir a IN_PROGRESS desde estado que no es COMPLETED retorna 400."""
        user = await create_authenticated_user(
            client, "revert_to_ip_wrong@test.com", "P@ssw0rd123!", "Revert", "Wrong"
        )

        comp = await create_competition(client, user["cookies"])

        # Competición está en DRAFT — no se puede revertir a IN_PROGRESS
        response = await client.put(
            f"/api/v1/competitions/{comp['id']}/revert-to-in-progress",
            cookies=user["cookies"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_reopen_enrollments_from_wrong_state_returns_400(self, client: AsyncClient):
        """Reabrir inscripciones desde ACTIVE (ya abierta) retorna 400."""
        user = await create_authenticated_user(
            client, "reopen_wrong@test.com", "P@ssw0rd123!", "Reopen", "Wrong"
        )

        comp = await create_competition(client, user["cookies"])

        # Activar competición — no se puede reabrir desde ACTIVE
        await client.post(f"/api/v1/competitions/{comp['id']}/activate", cookies=user["cookies"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/reopen-enrollments",
            cookies=user["cookies"],
        )

        assert response.status_code == 400


class TestEdgeCases:
    """Tests de edge cases para Competition"""

    @pytest.mark.asyncio
    async def test_create_competition_duplicate_name_returns_409(self, client: AsyncClient):
        """Crear competición con nombre duplicado retorna 409."""
        user = await create_authenticated_user(
            client, "dupname@test.com", "P@ssw0rd123!", "Dup", "Name"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Unique Name Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        # Primera creación
        await client.post("/api/v1/competitions", json=comp_data, cookies=user["cookies"])

        # Segunda con mismo nombre
        response = await client.post(
            "/api/v1/competitions", json=comp_data, cookies=user["cookies"]
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_while_enrollment_is_open_succeeds(self, client: AsyncClient):
        """BE #323: con las inscripciones abiertas todavía se corrige el montaje."""
        user = await create_authenticated_user(
            client, "update_active@test.com", "P@ssw0rd123!", "Update", "Active"
        )

        comp = await create_competition(client, user["cookies"])
        await activate_competition(client, user["cookies"], comp["id"])

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"name": "New Name"},
            cookies=user["cookies"],
        )

        assert response.status_code == 200

    async def test_update_after_enrollment_closes_returns_400(self, client: AsyncClient):
        """Cerradas las inscripciones se sortean equipos: ya no se toca."""
        user = await create_authenticated_user(
            client, "update_closed@test.com", "P@ssw0rd123!", "Update", "Closed"
        )

        comp = await create_competition(client, user["cookies"])
        await activate_competition(client, user["cookies"], comp["id"])
        await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=user["cookies"],
        )

        response = await client.put(
            f"/api/v1/competitions/{comp['id']}",
            json={"name": "New Name"},
            cookies=user["cookies"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_competition_with_is_creator_false(self, client: AsyncClient):
        """Ver competición de otro usuario tiene is_creator=false."""
        creator = await create_authenticated_user(
            client, "creator_check@test.com", "P@ssw0rd123!", "Creator", "Check"
        )
        viewer = await create_authenticated_user(
            client, "viewer@test.com", "P@ssw0rd123!", "Viewer", "User"
        )

        comp = await create_competition(client, creator["cookies"])

        response = await client.get(f"/api/v1/competitions/{comp['id']}", cookies=viewer["cookies"])

        assert response.status_code == 200
        assert response.json()["is_creator"] is False

    @pytest.mark.asyncio
    async def test_create_competition_with_invalid_country_returns_400(self, client: AsyncClient):
        """Crear competición con país inválido retorna 400."""
        user = await create_authenticated_user(
            client, "badcountry@test.com", "P@ssw0rd123!", "Bad", "Country"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Invalid Country Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "XX",  # País inválido
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        response = await client.post(
            "/api/v1/competitions", json=comp_data, cookies=user["cookies"]
        )

        # Podría ser 400 o 422 dependiendo de la validación
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_competition_with_non_adjacent_countries_returns_400(
        self, client: AsyncClient
    ):
        """Crear competición con países no adyacentes retorna 400."""
        user = await create_authenticated_user(
            client, "nonadjacent@test.com", "P@ssw0rd123!", "Non", "Adjacent"
        )

        start = date.today() + timedelta(days=30)
        end = start + timedelta(days=3)

        comp_data = {
            "name": "Non Adjacent Test",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "main_country": "ES",
            "adjacent_country_1": "JP",  # Japón no es adyacente a España
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
        }

        response = await client.post(
            "/api/v1/competitions", json=comp_data, cookies=user["cookies"]
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_competition_returns_400(self, client: AsyncClient):
        """Cancelar competición ya cancelada retorna 400."""
        user = await create_authenticated_user(
            client, "doublecancel@test.com", "P@ssw0rd123!", "Double", "Cancel"
        )

        comp = await create_competition(client, user["cookies"])

        # Primera cancelación
        await client.post(f"/api/v1/competitions/{comp['id']}/cancel", cookies=user["cookies"])

        # Segunda cancelación
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/cancel", cookies=user["cookies"]
        )

        assert response.status_code == 400


class TestCompetitionGolfCourses:
    """Tests para gestión de campos de golf en competiciones."""

    @pytest.mark.asyncio
    async def test_add_golf_course_to_competition_success(self, client: AsyncClient):
        """Añadir campo de golf aprobado a competición DRAFT es exitoso."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_add_gc@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "golf_creator@test.com", "P@ssw0rd123!", "Golf", "Creator"
        )

        # Crear competición en DRAFT
        comp = await create_competition(client, creator["cookies"])

        # Crear y aprobar campo de golf
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["competition_id"] == comp["id"]
        assert data["golf_course_id"] == golf_course["id"]
        assert data["display_order"] == 1
        assert "added_at" in data

    @pytest.mark.asyncio
    async def test_add_golf_course_not_creator_returns_403(self, client: AsyncClient):
        """Añadir campo por usuario que no es creador retorna 403."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_not_creator@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "comp_owner@test.com", "P@ssw0rd123!", "Owner", "User"
        )
        other_user = await create_authenticated_user(
            client, "other_user@test.com", "P@ssw0rd123!", "Other", "User"
        )

        comp = await create_competition(client, creator["cookies"])
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act
        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=other_user["cookies"],
        )

        # Assert
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_add_golf_course_once_enrollment_closes_returns_400(self, client: AsyncClient):
        """BE #323: con las inscripciones abiertas sí; cerradas, ya no.

        Justo el caso que motivó el cambio: quien invita antes de poner el campo
        —y con ello abre el torneo— tiene que poder ponerlo después.
        """
        # Arrange
        admin = await create_admin_user(
            client, "admin_not_draft@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "active_comp@test.com", "P@ssw0rd123!", "Active", "Comp"
        )

        comp = await create_competition(client, creator["cookies"])
        await activate_competition(client, creator["cookies"], comp["id"])

        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Con las inscripciones abiertas todavía se puede añadir
        abierta = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=creator["cookies"],
        )
        assert abierta.status_code == 201

        # Al cerrarlas, ya no
        await client.post(
            f"/api/v1/competitions/{comp['id']}/close-enrollments",
            cookies=creator["cookies"],
        )
        otro_campo = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], otro_campo["id"])

        response = await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": otro_campo["id"]},
            cookies=creator["cookies"],
        )

        assert response.status_code == 400
        assert "inscripciones" in response.text

    @pytest.mark.asyncio
    async def test_remove_golf_course_from_competition_success(self, client: AsyncClient):
        """Eliminar campo de golf de competición DRAFT es exitoso."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_remove_gc@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "remove_gc@test.com", "P@ssw0rd123!", "Remove", "GC"
        )

        comp = await create_competition(client, creator["cookies"])
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Añadir campo primero
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=creator["cookies"],
        )

        # Act
        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}/golf-courses/{golf_course['id']}",
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["competition_id"] == comp["id"]
        assert data["golf_course_id"] == golf_course["id"]
        assert "removed_at" in data

    @pytest.mark.asyncio
    async def test_remove_golf_course_not_assigned_returns_400(self, client: AsyncClient):
        """Eliminar campo no asociado retorna 400."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_unassigned@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "remove_unassigned@test.com", "P@ssw0rd123!", "Remove", "Unassigned"
        )

        comp = await create_competition(client, creator["cookies"])
        golf_course = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], golf_course["id"])

        # Act (intentar eliminar sin haber añadido)
        response = await client.delete(
            f"/api/v1/competitions/{comp['id']}/golf-courses/{golf_course['id']}",
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 400
        assert "no está" in response.text.lower() or "not" in response.text.lower()

    @pytest.mark.asyncio
    async def test_reorder_golf_courses_success(self, client: AsyncClient):
        """Reordenar campos de golf en competición DRAFT es exitoso."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_reorder@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "reorder_gc@test.com", "P@ssw0rd123!", "Reorder", "GC"
        )

        comp = await create_competition(client, creator["cookies"])

        # Crear y añadir 3 campos de golf
        gc1 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc1["id"])

        gc2 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc2["id"])

        gc3 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc3["id"])

        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc1["id"]},
            cookies=creator["cookies"],
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc2["id"]},
            cookies=creator["cookies"],
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc3["id"]},
            cookies=creator["cookies"],
        )

        # Act - Reordenar en orden inverso
        response = await client.put(
            f"/api/v1/competitions/{comp['id']}/golf-courses/reorder",
            json={"golf_course_ids": [gc3["id"], gc2["id"], gc1["id"]]},
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["competition_id"] == comp["id"]
        assert data["golf_course_count"] == 3
        assert "reordered_at" in data

        # Verificar nuevo orden
        list_response = await client.get(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            cookies=creator["cookies"],
        )
        golf_courses_list = list_response.json()
        assert golf_courses_list[0]["golf_course_id"] == gc3["id"]
        assert golf_courses_list[0]["display_order"] == 1
        assert golf_courses_list[1]["golf_course_id"] == gc2["id"]
        assert golf_courses_list[1]["display_order"] == 2
        assert golf_courses_list[2]["golf_course_id"] == gc1["id"]
        assert golf_courses_list[2]["display_order"] == 3

    @pytest.mark.asyncio
    async def test_reorder_golf_courses_missing_ids_returns_400(self, client: AsyncClient):
        """Reordenar con lista incompleta de IDs retorna 400."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_reorder_missing@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "reorder_missing@test.com", "P@ssw0rd123!", "Reorder", "Missing"
        )

        comp = await create_competition(client, creator["cookies"])

        gc1 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc1["id"])

        gc2 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc2["id"])

        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc1["id"]},
            cookies=creator["cookies"],
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc2["id"]},
            cookies=creator["cookies"],
        )

        # Act - Enviar solo 1 de los 2 IDs
        response = await client.put(
            f"/api/v1/competitions/{comp['id']}/golf-courses/reorder",
            json={"golf_course_ids": [gc1["id"]]},
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 400
        assert "especificar" in response.text.lower() or "expected" in response.text.lower()

    @pytest.mark.asyncio
    async def test_list_golf_courses_success(self, client: AsyncClient):
        """Listar campos de golf de una competición es exitoso."""
        # Arrange
        admin = await create_admin_user(
            client, "admin_list_gc@test.com", "AdminP@ssw0rd123!", "Admin", "Test"
        )

        creator = await create_authenticated_user(
            client, "list_gc@test.com", "P@ssw0rd123!", "List", "GC"
        )

        comp = await create_competition(client, creator["cookies"])

        gc1 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc1["id"])

        gc2 = await create_golf_course(client, creator["cookies"])
        await approve_golf_course(client, admin["cookies"], gc2["id"])

        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc1["id"]},
            cookies=creator["cookies"],
        )
        await client.post(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            json={"golf_course_id": gc2["id"]},
            cookies=creator["cookies"],
        )

        # Act
        response = await client.get(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        golf_courses = response.json()
        assert len(golf_courses) == 2
        assert golf_courses[0]["golf_course_id"] == gc1["id"]
        assert golf_courses[0]["display_order"] == 1
        assert golf_courses[1]["golf_course_id"] == gc2["id"]
        assert golf_courses[1]["display_order"] == 2

        # Verificar que incluye datos completos del campo
        assert "golf_course" in golf_courses[0]
        assert "name" in golf_courses[0]["golf_course"]
        assert "tees" in golf_courses[0]["golf_course"]
        assert "holes" in golf_courses[0]["golf_course"]

    @pytest.mark.asyncio
    async def test_list_golf_courses_empty_returns_empty_list(self, client: AsyncClient):
        """Listar campos de competición sin campos retorna lista vacía."""
        # Arrange
        creator = await create_authenticated_user(
            client, "list_empty@test.com", "P@ssw0rd123!", "List", "Empty"
        )

        comp = await create_competition(client, creator["cookies"])

        # Act
        response = await client.get(
            f"/api/v1/competitions/{comp['id']}/golf-courses",
            cookies=creator["cookies"],
        )

        # Assert
        assert response.status_code == 200
        golf_courses = response.json()
        assert len(golf_courses) == 0
        assert golf_courses == []

# Del reloj y no del calendario: una fecha fija hace que el test empiece a
# fallar solo el dia en que queda por detras de «ahora»


class TestScheduledEnrollmentOpening:
    """BE #319, #332: los dias de antelacion tienen que llegar y volver."""

    @pytest.mark.asyncio
    async def test_the_scheduled_days_survive_the_round_trip(self, client: AsyncClient):
        """Se manda al crear y se lee al consultar.

        Guardarla sin devolverla deja el formulario de edicion en blanco y al
        organizador creyendo que no se acepto.
        """
        user = await create_authenticated_user(
            client, "apertura@test.com", "P@ssw0rd123!", "Club", "Programado"
        )

        creada = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Torneo del club",
                "start_date": (datetime.now() + timedelta(days=60)).date().isoformat(),
                "end_date": (datetime.now() + timedelta(days=62)).date().isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "enrollment_opens_days_before": 5,
            },
            cookies=user["cookies"],
        )

        assert creada.status_code == 201
        assert creada.json()["enrollment_opens_days_before"] == 5

        detalle = await client.get(
            f"/api/v1/competitions/{creada.json()['id']}", cookies=user["cookies"]
        )

        assert detalle.status_code == 200
        assert detalle.json()["enrollment_opens_days_before"] == 5

    @pytest.mark.asyncio
    async def test_without_days_it_is_born_with_enrolment_open(self, client: AsyncClient):
        """Sin dias programados nace ABIERTA, en una sola llamada (BE #332).

        Nadie deberia pulsar un boton cuyo unico trabajo es mover un estado. Y
        va en la misma operacion: crear y activar por separado dejaria la
        competicion creada y cerrada si falla la segunda, con el organizador
        creyendo que esta abierta.
        """
        user = await create_authenticated_user(
            client, "nace_abierta@test.com", "P@ssw0rd123!", "Nace", "Abierta"
        )

        creada = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Torneo entre amigos",
                "start_date": (datetime.now() + timedelta(days=60)).date().isoformat(),
                "end_date": (datetime.now() + timedelta(days=62)).date().isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
            },
            cookies=user["cookies"],
        )

        assert creada.status_code == 201
        assert creada.json()["status"] == "ACTIVE"
        assert creada.json()["enrollment_opens_days_before"] is None

    @pytest.mark.asyncio
    async def test_with_days_it_waits_in_draft(self, client: AsyncClient):
        """Con dias puestos espera: DRAFT significa «esperando su hora»."""
        user = await create_authenticated_user(
            client, "espera_su_hora@test.com", "P@ssw0rd123!", "Espera", "SuHora"
        )

        creada = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Torneo del club",
                "start_date": (datetime.now() + timedelta(days=60)).date().isoformat(),
                "end_date": (datetime.now() + timedelta(days=62)).date().isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "enrollment_opens_days_before": 5,
            },
            cookies=user["cookies"],
        )

        assert creada.status_code == 201
        assert creada.json()["status"] == "DRAFT"

    @pytest.mark.asyncio
    async def test_more_than_a_fortnight_is_refused(self, client: AsyncClient):
        """Dos semanas es el tope: 15 dias no entra (BE #332).

        El rango se comprueba en la puerta, no solo en el dominio: un 15 que
        colara dejaria una apertura que nadie puede volver a elegir en la app.
        """
        user = await create_authenticated_user(
            client, "apertura_rango@test.com", "P@ssw0rd123!", "Club", "FueraDeRango"
        )

        respuesta = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Torneo del club",
                "start_date": "2026-11-01",
                "end_date": "2026-11-03",
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "enrollment_opens_days_before": 15,
            },
            cookies=user["cookies"],
        )

        assert respuesta.status_code == 422

    @pytest.mark.asyncio
    async def test_looking_at_it_after_the_opening_day_opens_it(self, client: AsyncClient):
        """Consultar la competicion pasada su hora es lo que la abre.

        No hay ningun proceso de fondo: si el endpoint no pasa por el caso de
        uso, la apertura programada no ocurre jamas y el torneo se queda en
        borrador para siempre. Este test existe para que eso no pueda volver.
        """
        admin = await create_admin_user(
            client, "admin_apertura@test.com", "AdminP@ssw0rd123!", "Admin", "Apertura"
        )
        user = await create_authenticated_user(
            client, "abre_sola@test.com", "P@ssw0rd123!", "Club", "AbreSola"
        )

        creada = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Torneo que ya abrio",
                "start_date": (datetime.now() + timedelta(days=3)).date().isoformat(),
                "end_date": (datetime.now() + timedelta(days=5)).date().isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "enrollment_opens_days_before": 5,
            },
            cookies=user["cookies"],
        )
        assert creada.status_code == 201
        assert creada.json()["status"] == "DRAFT"

        # La zona sale del campo que se juega: sin campo, la apertura espera
        competicion_id = creada.json()["id"]
        # Con coordenadas: la zona sale de ahi, no del pais (BE #305)
        golf_course = await create_golf_course(
            client,
            user["cookies"],
            golf_course_data={
                "name": f"Campo con zona {uuid.uuid4().hex[:8]}",
                "country_code": "ES",
                "course_type": "STANDARD_18",
                "location": {"latitude": 40.4168, "longitude": -3.7038},
                "tees": [
                    {
                        "identifier": "Blanco",
                        "color": "WHITE",
                        "tee_gender": "MALE",
                        "course_rating": 72.5,
                        "slope_rating": 135,
                        "par": 72,
                    },
                ],
                "holes": [
                    {"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)
                ],
            },
        )
        await approve_golf_course(client, admin["cookies"], golf_course["id"])
        anadido = await client.post(
            f"/api/v1/competitions/{competicion_id}/golf-courses",
            json={"golf_course_id": golf_course["id"]},
            cookies=user["cookies"],
        )
        assert anadido.status_code == 201, anadido.text

        creado = await client.get(
            f"/api/v1/golf-courses/{golf_course['id']}", cookies=user["cookies"]
        )
        assert creado.json().get("timezone") == "Europe/Madrid", creado.text[:200]

        detalle = await client.get(
            f"/api/v1/competitions/{competicion_id}", cookies=user["cookies"]
        )

        assert detalle.status_code == 200
        assert detalle.json()["status"] == "ACTIVE"


class TestPublicAndPrivate:
    """BE #318: una privada no se le ensena a quien no esta dentro."""

    @pytest.mark.asyncio
    async def test_a_stranger_does_not_see_a_private_competition(self, client: AsyncClient):
        """La Ryder de unos amigos no sale en la pantalla de explorar."""
        organizador = await create_authenticated_user(
            client, "organiza_privada@test.com", "P@ssw0rd123!", "Organiza", "Privada"
        )
        creada = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Ryder de los amigos",
                "start_date": (datetime.now() + timedelta(days=60)).date().isoformat(),
                "end_date": (datetime.now() + timedelta(days=62)).date().isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
            },
            cookies=organizador["cookies"],
        )
        assert creada.status_code == 201
        assert creada.json()["visibility"] == "PRIVATE", "nace privada"

        desconocido = await create_authenticated_user(
            client, "curioso@test.com", "P@ssw0rd123!", "Un", "Curioso"
        )
        explorar = await client.get(
            "/api/v1/competitions?my_competitions=false", cookies=desconocido["cookies"]
        )

        assert explorar.status_code == 200
        ids = [c["id"] for c in explorar.json()]
        assert creada.json()["id"] not in ids

    @pytest.mark.asyncio
    async def test_a_stranger_does_see_a_public_one(self, client: AsyncClient):
        organizador = await create_authenticated_user(
            client, "organiza_publica@test.com", "P@ssw0rd123!", "Organiza", "Publica"
        )
        creada = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Campeonato del club",
                "start_date": (datetime.now() + timedelta(days=60)).date().isoformat(),
                "end_date": (datetime.now() + timedelta(days=62)).date().isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "visibility": "PUBLIC",
            },
            cookies=organizador["cookies"],
        )
        assert creada.status_code == 201
        assert creada.json()["visibility"] == "PUBLIC"

        desconocido = await create_authenticated_user(
            client, "curioso2@test.com", "P@ssw0rd123!", "Otro", "Curioso"
        )
        explorar = await client.get(
            "/api/v1/competitions?my_competitions=false", cookies=desconocido["cookies"]
        )

        ids = [c["id"] for c in explorar.json()]
        assert creada.json()["id"] in ids

    @pytest.mark.asyncio
    async def test_asking_for_a_place_in_a_private_one_is_refused_cleanly(
        self, client: AsyncClient
    ):
        """Y se rechaza con un 403, no con un 500.

        Toda competicion que ya existe pasa a PRIVATE con la migracion, asi que
        este es el camino por defecto del boton de pedir plaza: una excepcion
        sin capturar aqui es un error del servidor en produccion.
        """
        organizador = await create_authenticated_user(
            client, "organiza_403@test.com", "P@ssw0rd123!", "Organiza", "Cerrada"
        )
        creada = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Ryder cerrada",
                "start_date": (datetime.now() + timedelta(days=60)).date().isoformat(),
                "end_date": (datetime.now() + timedelta(days=62)).date().isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
            },
            cookies=organizador["cookies"],
        )
        competicion_id = creada.json()["id"]
        await client.post(
            f"/api/v1/competitions/{competicion_id}/activate", cookies=organizador["cookies"]
        )

        desconocido = await create_authenticated_user(
            client, "pide_plaza@test.com", "P@ssw0rd123!", "Pide", "Plaza"
        )
        respuesta = await client.post(
            f"/api/v1/competitions/{competicion_id}/enrollments",
            cookies=desconocido["cookies"],
        )

        assert respuesta.status_code == 403, respuesta.text

    @pytest.mark.asyncio
    async def test_somebody_rejected_cannot_pull_it_back_through_my_competitions(
        self, client: AsyncClient
    ):
        """El expulsado no la recupera por «mis competiciones».

        Es el camino gemelo del listado: las competiciones que salen de tus
        inscripciones se anadian DESPUES del filtro de visibilidad, y las filas
        rechazadas y retiradas no se borran.
        """
        organizador = await create_authenticated_user(
            client, "organiza_gemelo@test.com", "P@ssw0rd123!", "Organiza", "Gemelo"
        )
        creada = await client.post(
            "/api/v1/competitions",
            json={
                "name": "Ryder con puerta",
                "start_date": (datetime.now() + timedelta(days=60)).date().isoformat(),
                "end_date": (datetime.now() + timedelta(days=62)).date().isoformat(),
                "main_country": "ES",
                "play_mode": "SCRATCH",
                "visibility": "PUBLIC",
            },
            cookies=organizador["cookies"],
        )
        competicion_id = creada.json()["id"]
        await client.post(
            f"/api/v1/competitions/{competicion_id}/activate", cookies=organizador["cookies"]
        )

        # Pide plaza mientras es publica, y se la rechazan
        rechazado = await create_authenticated_user(
            client, "rechazado@test.com", "P@ssw0rd123!", "Le", "Rechazan"
        )
        pedida = await client.post(
            f"/api/v1/competitions/{competicion_id}/enrollments", cookies=rechazado["cookies"]
        )
        assert pedida.status_code == 201, pedida.text
        rechazo = await client.post(
            f"/api/v1/enrollments/{pedida.json()['id']}/reject", cookies=organizador["cookies"]
        )
        assert rechazo.status_code == 200, rechazo.text

        # Y el torneo se cierra al publico
        await client.put(
            f"/api/v1/competitions/{competicion_id}",
            json={"visibility": "PRIVATE"},
            cookies=organizador["cookies"],
        )

        mias = await client.get(
            "/api/v1/competitions?my_competitions=true", cookies=rechazado["cookies"]
        )

        assert mias.status_code == 200
        assert competicion_id not in [c["id"] for c in mias.json()]




@pytest.mark.integration
class TestCanDeleteEnLaFicha:
    """
    La ficha dice si quien la mira puede borrarla ahora (BE #347), para que la
    app enseñe el botón solo cuando el borrado va a funcionar. En los listados
    no se calcula: sería mirar el calendario de cada competición de la lista.
    """

    @pytest.mark.asyncio
    async def test_i1_el_creador_de_una_abierta_sin_calendario_puede(self, client: AsyncClient):
        creador = await create_authenticated_user(
            client, "cd-creador@test.com", "P@ssw0rd123!", "Can", "Delete"
        )
        comp = await create_competition(client, creador["cookies"])

        client.cookies.clear()
        client.cookies.update(creador["cookies"])
        ficha = await client.get(f"/api/v1/competitions/{comp['id']}")

        assert ficha.status_code == 200, ficha.text
        assert ficha.json()["can_delete"] is True

    @pytest.mark.asyncio
    async def test_i2_otro_usuario_no_puede(self, client: AsyncClient):
        creador = await create_authenticated_user(
            client, "cd-creador2@test.com", "P@ssw0rd123!", "Can", "Delete"
        )
        otro = await create_authenticated_user(
            client, "cd-otro@test.com", "P@ssw0rd123!", "Otro", "Usuario"
        )
        comp = await create_competition(client, creador["cookies"])

        client.cookies.clear()
        client.cookies.update(otro["cookies"])
        ficha = await client.get(f"/api/v1/competitions/{comp['id']}")

        assert ficha.status_code == 200
        assert ficha.json()["can_delete"] is False

    @pytest.mark.asyncio
    async def test_i3_en_los_listados_no_se_calcula(self, client: AsyncClient):
        creador = await create_authenticated_user(
            client, "cd-creador3@test.com", "P@ssw0rd123!", "Can", "Delete"
        )
        await create_competition(client, creador["cookies"])

        client.cookies.clear()
        client.cookies.update(creador["cookies"])
        listado = await client.get("/api/v1/competitions", params={"my_competitions": True})

        assert listado.status_code == 200
        competiciones = listado.json()
        assert competiciones
        assert all(c.get("can_delete") is None for c in competiciones)
