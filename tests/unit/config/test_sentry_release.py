"""
La release que el backend declara a Sentry.

Antes iba fija a `rydercup-backend@1.8.0` y todos los errores de producción
aparecían en Sentry como de una versión de hace meses. Ahora sale de la misma
fuente que `GET /health` (`src.config.version.APP_VERSION`), así que basta con
subir la versión en la release para que Sentry la vea. Si la versión no se
conoce, se dice `unknown`; nunca se inventa un número.
"""

from unittest.mock import patch

import pytest

from src.config import sentry_config, version

DSN = "https://public@o0.ingest.sentry.io/0"


def _release_con_la_que_se_inicia(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(sentry_config.settings, "SENTRY_DSN", DSN)
    with patch.object(sentry_config.sentry_sdk, "init") as init:
        sentry_config.init_sentry()
    init.assert_called_once()
    return init.call_args.kwargs["release"]


class TestReleaseDeSentry:
    async def test_s1_la_release_es_la_version_que_expone_health(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Contra lo que responde `/health`, no contra la constante: si `/health`
        # cambiara de fuente, Sentry y `/health` se separarían sin avisar
        import main

        salud = await main.health()

        assert _release_con_la_que_se_inicia(monkeypatch) == f"rydercup-backend@{salud.version}"

    def test_s1_la_release_sigue_a_la_fuente_unica_al_cambiar_la_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Si hubiera una segunda versión escrita a mano, esto la delataría
        monkeypatch.setattr(version, "APP_VERSION", "9.8.7")

        assert _release_con_la_que_se_inicia(monkeypatch) == "rydercup-backend@9.8.7"

    @pytest.mark.parametrize("desconocida", ["", "   "])
    def test_s2_version_desconocida_se_declara_unknown(
        self, monkeypatch: pytest.MonkeyPatch, desconocida: str
    ) -> None:
        monkeypatch.setattr(version, "APP_VERSION", desconocida)

        assert _release_con_la_que_se_inicia(monkeypatch) == "rydercup-backend@unknown"

    def test_s2_la_version_se_declara_sin_espacios_sobrantes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(version, "APP_VERSION", " 2.40.1 ")

        assert _release_con_la_que_se_inicia(monkeypatch) == "rydercup-backend@2.40.1"


class TestComportamientoQueNoCambia:
    def test_sin_dsn_sentry_no_se_inicia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sentry_config.settings, "SENTRY_DSN", "")
        with patch.object(sentry_config.sentry_sdk, "init") as init:
            sentry_config.init_sentry()

        init.assert_not_called()

    def test_con_dsn_conserva_muestreo_filtros_y_privacidad(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sentry_config.settings, "SENTRY_DSN", DSN)
        monkeypatch.setattr(sentry_config.settings, "SENTRY_ENVIRONMENT", "production")
        monkeypatch.setattr(sentry_config.settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1)
        monkeypatch.setattr(sentry_config.settings, "SENTRY_PROFILES_SAMPLE_RATE", 0.2)
        with patch.object(sentry_config.sentry_sdk, "init") as init:
            sentry_config.init_sentry()

        kwargs = init.call_args.kwargs
        assert kwargs["dsn"] == DSN
        assert kwargs["environment"] == "production"
        assert kwargs["traces_sample_rate"] == 0.1
        assert kwargs["profiles_sample_rate"] == 0.2
        assert kwargs["before_send"] is sentry_config.before_send
        assert kwargs["send_default_pii"] is False
        assert kwargs["include_local_variables"] is False
        assert kwargs["max_breadcrumbs"] == 50
        assert kwargs["debug"] is False
