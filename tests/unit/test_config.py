import pytest

from app.config import Settings


def test_la_conexion_a_mongodb_tiene_valores_por_defecto() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url == "mongodb://localhost:27017"
    assert settings.database_name == "document_store"
    assert settings.database_timeout_ms == 3000


def test_la_conexion_a_mongodb_se_configura_por_variables_de_entorno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "mongodb://mongo:27017")
    monkeypatch.setenv("DATABASE_NAME", "documentos")
    monkeypatch.setenv("DATABASE_TIMEOUT_MS", "500")

    settings = Settings(_env_file=None)

    assert settings.database_url == "mongodb://mongo:27017"
    assert settings.database_name == "documentos"
    assert settings.database_timeout_ms == 500


def test_el_apagado_ordenado_espera_10_segundos_por_defecto() -> None:
    settings = Settings(_env_file=None)

    # Menor que el stop_grace_period de 15 s del compose: uvicorn termina de
    # cerrar antes de que Docker mate el proceso.
    assert settings.graceful_shutdown_seconds == 10


def test_el_apagado_ordenado_se_configura_por_variable_de_entorno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GRACEFUL_SHUTDOWN_SECONDS", "5")

    assert Settings(_env_file=None).graceful_shutdown_seconds == 5
