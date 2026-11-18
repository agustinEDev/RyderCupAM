"""
El repositorio en memoria se comporta como el real con nombres repetidos (S-16): con dos
o más cuentas activas con ese nombre, «no encontrado». Ver
tests/integration/.../test_homonimos_en_postgres.py.
"""

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_user_repository import (
    InMemoryUserRepository,
)

pytestmark = pytest.mark.asyncio


def _usuario(nombre: str, apellidos: str, correo: str, activa: bool = True) -> User:
    usuario = User.create(
        first_name=nombre, last_name=apellidos, email_str=correo, plain_password="ValidPassword123!"
    )
    if not activa:
        usuario.deactivate()
    return usuario


async def test_two_active_homonyms_give_not_found():
    repo = InMemoryUserRepository()
    await repo.save(_usuario("Ana", "Ruiz", "a1@example.com"))
    await repo.save(_usuario("Ana", "Ruiz", "a2@example.com"))

    assert await repo.find_by_full_name("Ana Ruiz") is None


async def test_one_active_and_one_deactivated_give_the_active_one():
    repo = InMemoryUserRepository()
    activa = _usuario("Luis", "Gil", "l1@example.com")
    await repo.save(activa)
    await repo.save(_usuario("Luis", "Gil", "l2@example.com", activa=False))

    encontrado = await repo.find_by_full_name("luis gil")

    assert encontrado is not None and encontrado.id == activa.id
