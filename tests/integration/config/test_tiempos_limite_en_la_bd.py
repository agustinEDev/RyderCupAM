"""
Los tiempos límite de la conexión los aplica de verdad Postgres (auditoría de la fase 6,
DB-04): con los mismos ajustes que la app, contra la base de los tests.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config.database import AJUSTES_DE_LA_CONEXION

pytestmark = pytest.mark.asyncio


def _url() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


async def test_t1_t2_postgres_applies_the_connection_timeouts():
    motor = create_async_engine(_url(), connect_args=AJUSTES_DE_LA_CONEXION)
    try:
        async with motor.connect() as conexion:
            consulta = await conexion.execute(text("SHOW statement_timeout"))
            assert consulta.scalar() == "15s"
            espera = await conexion.execute(text("SHOW idle_in_transaction_session_timeout"))
            assert espera.scalar() == "30s"
    finally:
        await motor.dispose()


async def test_t1_a_statement_over_the_limit_is_cut():
    ajustes = {"server_settings": {**AJUSTES_DE_LA_CONEXION["server_settings"]}}
    ajustes["server_settings"]["statement_timeout"] = "200"
    motor = create_async_engine(_url(), connect_args=ajustes)
    try:
        async with motor.connect() as conexion:
            with pytest.raises(Exception, match="statement timeout"):
                await conexion.execute(text("SELECT pg_sleep(2)"))
    finally:
        await motor.dispose()
