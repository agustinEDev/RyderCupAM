"""
La fábrica de tipos de persistencia de ids (`tipo_de_id`).

  #   | entrada al guardar                  | columna texto        | columna uuid
  ----|-------------------------------------|----------------------|------------------
  G1  | el id                               | su UUID en texto     | su UUID
  G2  | un texto                            | tal cual             | convertido a UUID
  G3  | un uuid.UUID                        | en texto             | tal cual
  G4  | None                                | NULL                 | NULL
  G5  | cualquier otra cosa                 | TypeError            | TypeError
  G6  | un id de OTRA clase                 | TypeError            | TypeError

  #   | al leer                             | columna texto        | columna uuid
  ----|-------------------------------------|----------------------|------------------
  L1  | un valor                            | el id con su UUID    | el id con su UUID
  L2  | NULL                                | None                 | None

  F1  | cada llamada da un tipo propio (cada módulo, el suyo)
  F2  | el tipo se llama como el id y lleva cache_ok
  F3  | columna texto: CHAR(36); "varchar": VARCHAR(36), como en la BD
"""

import uuid
from dataclasses import dataclass

import pytest
import sqlalchemy

from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.infrastructure.persistence.sqlalchemy.tipos_de_id import (
    tipo_de_codigo_de_pais,
    tipo_de_id,
)

UN_UUID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


class IdDePrueba:
    def __init__(self, value: uuid.UUID):
        self.value = value


@dataclass(frozen=True)
class OtroId:
    value: uuid.UUID


TEXTO = tipo_de_id(IdDePrueba)()
NATIVO = tipo_de_id(IdDePrueba, columna="uuid")()


def guarda(tipo, valor):
    return tipo.process_bind_param(valor, None)


def lee(tipo, valor):
    return tipo.process_result_value(valor, None)


class TestAlGuardar:
    def test_g1_el_id(self):
        assert guarda(TEXTO, IdDePrueba(UN_UUID)) == str(UN_UUID)
        assert guarda(NATIVO, IdDePrueba(UN_UUID)) == UN_UUID

    def test_g2_un_texto(self):
        assert guarda(TEXTO, str(UN_UUID)) == str(UN_UUID)
        assert guarda(NATIVO, str(UN_UUID)) == UN_UUID

    def test_g3_un_uuid(self):
        assert guarda(TEXTO, UN_UUID) == str(UN_UUID)
        assert guarda(NATIVO, UN_UUID) == UN_UUID

    def test_g4_none_es_null(self):
        assert guarda(TEXTO, None) is None
        assert guarda(NATIVO, None) is None

    @pytest.mark.parametrize("raro", [123, 1.5, b"x", object(), [UN_UUID]])
    def test_g5_cualquier_otra_cosa_es_un_error(self, raro):
        for tipo in (TEXTO, NATIVO):
            with pytest.raises(TypeError, match="IdDePrueba"):
                guarda(tipo, raro)

    def test_g6_un_id_de_otra_clase_es_un_error(self):
        for tipo in (TEXTO, NATIVO):
            with pytest.raises(TypeError, match="OtroId"):
                guarda(tipo, OtroId(UN_UUID))


class TestAlLeer:
    def test_l1_un_valor_da_el_id(self):
        leido = lee(TEXTO, str(UN_UUID))
        assert isinstance(leido, IdDePrueba)
        assert leido.value == UN_UUID
        leido = lee(NATIVO, UN_UUID)
        assert isinstance(leido, IdDePrueba)
        assert leido.value == UN_UUID

    def test_l1_un_dataclass_tambien(self):
        assert lee(tipo_de_id(OtroId)(), str(UN_UUID)) == OtroId(UN_UUID)

    def test_l2_null_da_none(self):
        assert lee(TEXTO, None) is None
        assert lee(NATIVO, None) is None


class TestLaFabrica:
    def test_f1_cada_llamada_da_un_tipo_propio(self):
        assert tipo_de_id(IdDePrueba) is not tipo_de_id(IdDePrueba)

    def test_f2_nombre_columna_y_cache(self):
        tipo = tipo_de_id(IdDePrueba)
        assert tipo.__name__ == "IdDePruebaType"
        assert tipo.cache_ok is True
        assert isinstance(TEXTO.impl, sqlalchemy.types.CHAR)
        assert TEXTO.impl.length == 36
        assert isinstance(NATIVO.impl, sqlalchemy.types.Uuid)

    def test_f3_columna_varchar_como_en_la_bd(self):
        # refresh_tokens.* son VARCHAR(36) en las migraciones: se declaran igual
        variable = tipo_de_id(IdDePrueba, columna="varchar")()
        assert type(variable.impl) is sqlalchemy.types.String
        assert variable.impl.length == 36
        assert type(TEXTO.impl) is sqlalchemy.types.CHAR
        assert guarda(variable, UN_UUID) == str(UN_UUID)
        assert lee(variable, str(UN_UUID)).value == UN_UUID


class TestCodigoDePais:
    """
    El tipo del código de país (`tipo_de_codigo_de_pais`), con las mismas
    reglas: el código o un texto se guardan, None es NULL, lo demás TypeError;
    al leer, el CountryCode.
    """

    PAIS = tipo_de_codigo_de_pais()()

    def test_guarda_el_codigo_o_un_texto(self):
        assert guarda(self.PAIS, CountryCode("ES")) == "ES"
        assert guarda(self.PAIS, "FR") == "FR"
        assert guarda(self.PAIS, None) is None

    @pytest.mark.parametrize("raro", [123, UN_UUID, object()])
    def test_lo_demas_es_un_error(self, raro):
        with pytest.raises(TypeError, match="CountryCode"):
            guarda(self.PAIS, raro)

    def test_al_leer_el_countrycode(self):
        assert lee(self.PAIS, "ES") == CountryCode("ES")
        assert lee(self.PAIS, None) is None

    def test_columna_de_dos_letras_y_un_tipo_por_llamada(self):
        assert isinstance(self.PAIS.impl, sqlalchemy.types.CHAR)
        assert self.PAIS.impl.length == 2
        assert tipo_de_codigo_de_pais() is not tipo_de_codigo_de_pais()
        assert tipo_de_codigo_de_pais().cache_ok is True

    def test_columna_varchar_como_en_la_bd(self):
        # golf_courses.country_code es VARCHAR(2) en las migraciones
        variable = tipo_de_codigo_de_pais(columna="varchar")()
        assert type(variable.impl) is sqlalchemy.types.String
        assert variable.impl.length == 2
        assert type(self.PAIS.impl) is sqlalchemy.types.CHAR
