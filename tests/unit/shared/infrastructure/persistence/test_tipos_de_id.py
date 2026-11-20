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
    def test_guardar_el_id_da_su_uuid(self):
        """
        Given: un id
        When: se guarda en columna de texto y en una uuid
        Then: su UUID en texto / su UUID
        """
        assert guarda(TEXTO, IdDePrueba(UN_UUID)) == str(UN_UUID)
        assert guarda(NATIVO, IdDePrueba(UN_UUID)) == UN_UUID

    def test_guardar_un_texto_lo_acepta(self):
        """
        Given: un texto con un UUID
        When: se guarda
        Then: tal cual en texto; convertido a UUID en la columna uuid
        """
        assert guarda(TEXTO, str(UN_UUID)) == str(UN_UUID)
        assert guarda(NATIVO, str(UN_UUID)) == UN_UUID

    def test_guardar_un_uuid_lo_acepta(self):
        """
        Given: un uuid.UUID
        When: se guarda
        Then: en texto / tal cual
        """
        assert guarda(TEXTO, UN_UUID) == str(UN_UUID)
        assert guarda(NATIVO, UN_UUID) == UN_UUID

    def test_guardar_none_da_null(self):
        """
        Given: None
        When: se guarda
        Then: NULL
        """
        assert guarda(TEXTO, None) is None
        assert guarda(NATIVO, None) is None

    @pytest.mark.parametrize("raro", [123, 1.5, b"x", object(), [UN_UUID]])
    def test_guardar_otro_tipo_lanza_typeerror(self, raro):
        """
        Given: un valor que no es id, texto, UUID ni None
        When: se guarda
        Then: TypeError con el nombre del id
        """
        for tipo in (TEXTO, NATIVO):
            with pytest.raises(TypeError, match="IdDePrueba"):
                guarda(tipo, raro)

    def test_guardar_un_id_de_otra_clase_lanza_typeerror(self):
        """
        Given: un id de otra clase
        When: se guarda
        Then: TypeError con el nombre de esa clase
        """
        for tipo in (TEXTO, NATIVO):
            with pytest.raises(TypeError, match="OtroId"):
                guarda(tipo, OtroId(UN_UUID))


class TestAlLeer:
    def test_leer_un_valor_da_el_id_con_su_uuid(self):
        """
        Given: un valor de la BD (texto o UUID)
        When: se lee
        Then: el id con su UUID dentro
        """
        leido = lee(TEXTO, str(UN_UUID))
        assert isinstance(leido, IdDePrueba)
        assert leido.value == UN_UUID
        leido = lee(NATIVO, UN_UUID)
        assert isinstance(leido, IdDePrueba)
        assert leido.value == UN_UUID

    def test_leer_un_valor_en_un_dataclass_da_el_id(self):
        """
        Given: un id que es un dataclass
        When: se lee un texto
        Then: el id con su UUID
        """
        assert lee(tipo_de_id(OtroId)(), str(UN_UUID)) == OtroId(UN_UUID)

    def test_leer_null_da_none(self):
        """
        Given: NULL
        When: se lee
        Then: None
        """
        assert lee(TEXTO, None) is None
        assert lee(NATIVO, None) is None


class TestLaFabrica:
    def test_fabricar_dos_veces_da_dos_tipos(self):
        """
        Given: la misma clase de id
        When: se fabrica dos veces
        Then: dos tipos distintos (cada módulo, el suyo)
        """
        assert tipo_de_id(IdDePrueba) is not tipo_de_id(IdDePrueba)

    def test_fabricar_da_nombre_columna_y_cache_ok(self):
        """
        Given: una clase de id
        When: se fabrica su tipo
        Then: se llama como el id, lleva cache_ok y su columna
        """
        tipo = tipo_de_id(IdDePrueba)
        assert tipo.__name__ == "IdDePruebaType"
        assert tipo.cache_ok is True
        assert isinstance(TEXTO.impl, sqlalchemy.types.CHAR)
        assert TEXTO.impl.length == 36
        assert isinstance(NATIVO.impl, sqlalchemy.types.Uuid)

    def test_fabricar_con_varchar_da_varchar_36(self):
        """
        Given: una tabla con VARCHAR(36)
        When: se fabrica con columna="varchar"
        Then: String(36), con las mismas reglas
        """
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

    def test_guardar_pais_codigo_o_texto_lo_acepta(self):
        """
        Given: un CountryCode, un texto o None
        When: se guarda
        Then: el código / tal cual / NULL
        """
        assert guarda(self.PAIS, CountryCode("ES")) == "ES"
        assert guarda(self.PAIS, "FR") == "FR"
        assert guarda(self.PAIS, None) is None

    @pytest.mark.parametrize("raro", [123, UN_UUID, object()])
    def test_guardar_pais_otro_tipo_lanza_typeerror(self, raro):
        """
        Given: un valor que no es código ni texto
        When: se guarda
        Then: TypeError
        """
        with pytest.raises(TypeError, match="CountryCode"):
            guarda(self.PAIS, raro)

    def test_leer_pais_da_el_countrycode(self):
        """
        Given: un código o NULL
        When: se lee
        Then: el CountryCode o None
        """
        assert lee(self.PAIS, "ES") == CountryCode("ES")
        assert lee(self.PAIS, None) is None

    def test_fabricar_pais_da_char_2_y_un_tipo_por_llamada(self):
        """
        Given: el tipo de país
        When: se fabrica
        Then: CHAR(2), cache_ok y un tipo por llamada
        """
        assert isinstance(self.PAIS.impl, sqlalchemy.types.CHAR)
        assert self.PAIS.impl.length == 2
        assert tipo_de_codigo_de_pais() is not tipo_de_codigo_de_pais()
        assert tipo_de_codigo_de_pais().cache_ok is True

    def test_fabricar_pais_con_varchar_da_varchar_2(self):
        """
        Given: una tabla con VARCHAR(2)
        When: se fabrica con columna="varchar"
        Then: String(2)
        """
        # golf_courses.country_code es VARCHAR(2) en las migraciones
        variable = tipo_de_codigo_de_pais(columna="varchar")()
        assert type(variable.impl) is sqlalchemy.types.String
        assert variable.impl.length == 2
        assert type(self.PAIS.impl) is sqlalchemy.types.CHAR
