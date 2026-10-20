"""
Tests del mapper del listado de inscripciones (BE #314).

Sin el límite oculto de 100, el listado devuelve todas las filas de la
competición: buscar a cada usuario por separado eran cientos de consultas
seguidas. Los usuarios se leen ahora en bloque, en UNA consulta.
"""

from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.infrastructure.api.v1.enrollment_routes import EnrollmentDTOMapper
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


class _UoWQueCuenta(InMemoryUnitOfWork):
    """UoW de usuarios en memoria que cuenta cuántas veces se abre y se consulta."""

    def __init__(self):
        super().__init__()
        self.aperturas = 0
        self.por_id = 0
        self.en_bloque: list[list[UserId]] = []
        repo = self._users
        original_por_id = repo.find_by_id
        original_en_bloque = repo.find_by_ids

        async def por_id(user_id):
            self.por_id += 1
            return await original_por_id(user_id)

        async def en_bloque(user_ids):
            self.en_bloque.append(list(user_ids))
            return await original_en_bloque(user_ids)

        repo.find_by_id = por_id  # type: ignore[method-assign]
        repo.find_by_ids = en_bloque  # type: ignore[method-assign]

    async def __aenter__(self):
        self.aperturas += 1
        return await super().__aenter__()


async def _usuario(uow: InMemoryUnitOfWork, nombre: str, alias: str | None = None) -> User:
    user = User.create(
        nombre, "Pérez", f"{nombre.lower()}-{uuid4().hex[:6]}@test.com", "P@ssw0rd123!"
    )
    if alias:
        user.update_profile(alias=alias)
    await uow.users.save(user)
    return user


def _inscripcion(competition_id: CompetitionId, user: User, use_real_name: bool = True):
    enrollment = Enrollment.direct_enroll(
        id=EnrollmentId.generate(), competition_id=competition_id, user_id=user.id
    )
    enrollment.set_name_preference(use_real_name)
    return enrollment


@pytest.fixture
def competition_id() -> CompetitionId:
    return CompetitionId(uuid4())


async def test_reads_every_user_in_one_query(competition_id):
    """Tres inscritos: una sola apertura del UoW y una sola consulta en bloque, ninguna por id."""
    uow = _UoWQueCuenta()
    usuarios = [await _usuario(uow, n) for n in ("Ana", "Bea", "Carla")]
    inscripciones = [_inscripcion(competition_id, u) for u in usuarios]

    await EnrollmentDTOMapper.to_response_dtos(inscripciones, uow)

    assert uow.aperturas == 1
    assert uow.por_id == 0
    assert len(uow.en_bloque) == 1
    assert sorted(map(str, uow.en_bloque[0])) == sorted(str(u.id) for u in usuarios)


async def test_a_user_with_several_rows_is_asked_for_once(competition_id):
    """Quien se dio de alta otra vez tiene varias filas: su id va una sola vez a la consulta."""
    uow = _UoWQueCuenta()
    ana = await _usuario(uow, "Ana")
    inscripciones = [_inscripcion(competition_id, ana), _inscripcion(competition_id, ana)]

    dtos = await EnrollmentDTOMapper.to_response_dtos(inscripciones, uow)

    assert uow.en_bloque == [[ana.id]]
    assert [d.user.first_name for d in dtos] == ["Ana", "Ana"]


async def test_keeps_the_order_of_the_enrollments_and_pairs_each_with_its_user(competition_id):
    uow = _UoWQueCuenta()
    usuarios = [await _usuario(uow, n) for n in ("Ana", "Bea", "Carla")]
    inscripciones = [_inscripcion(competition_id, u) for u in reversed(usuarios)]

    dtos = await EnrollmentDTOMapper.to_response_dtos(inscripciones, uow)

    assert [d.id for d in dtos] == [e.id.value for e in inscripciones]
    assert [d.user.id for d in dtos] == [e.user_id.value for e in inscripciones]
    assert [d.user.first_name for d in dtos] == ["Carla", "Bea", "Ana"]


async def test_an_enrollment_whose_user_no_longer_exists_comes_without_user(competition_id):
    """Como antes: `user` a None para esa fila, y las demás intactas."""
    uow = _UoWQueCuenta()
    ana = await _usuario(uow, "Ana")
    fantasma = User.create("Fantasma", "Nadie", "fantasma@test.com", "P@ssw0rd123!")
    inscripciones = [_inscripcion(competition_id, fantasma), _inscripcion(competition_id, ana)]

    dtos = await EnrollmentDTOMapper.to_response_dtos(inscripciones, uow)

    assert dtos[0].user is None
    assert dtos[0].user_id == fantasma.id.value
    assert dtos[1].user.first_name == "Ana"


async def test_the_name_follows_the_preference_of_each_enrollment(competition_id):
    """El alias o el nombre legal lo decide SU inscripción, no el perfil (BE #254)."""
    uow = _UoWQueCuenta()
    con_nombre = await _usuario(uow, "Ana", alias="Anita")
    con_alias = await _usuario(uow, "Bea", alias="Beíta")
    inscripciones = [
        _inscripcion(competition_id, con_nombre, use_real_name=True),
        _inscripcion(competition_id, con_alias, use_real_name=False),
    ]

    dtos = await EnrollmentDTOMapper.to_response_dtos(inscripciones, uow)

    assert [d.user.display_name for d in dtos] == ["Ana Pérez", "Beíta"]


async def test_no_enrollments_no_query():
    uow = _UoWQueCuenta()

    assert await EnrollmentDTOMapper.to_response_dtos([], uow) == []
    assert uow.en_bloque == []
    assert uow.por_id == 0


async def test_categories_reach_each_enrollment(competition_id):
    """Con la categoría fijada, cada fila lleva la suya y su hándicap fijado (#251)."""
    uow = _UoWQueCuenta()
    ana = await _usuario(uow, "Ana")
    bea = await _usuario(uow, "Bea")
    inscripciones = [_inscripcion(competition_id, ana), _inscripcion(competition_id, bea)]

    dtos = await EnrollmentDTOMapper.to_response_dtos(
        inscripciones, uow, categorias={ana.id: 1, bea.id: 2}
    )

    assert [d.category for d in dtos] == [1, 2]
