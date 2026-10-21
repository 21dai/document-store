"""`.env.example` documenta toda la configuración, sin credenciales reales."""

from pathlib import Path

from pydantic_settings import DotEnvSettingsSource

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def variables_del_env_example() -> dict[str, str | None]:
    source = DotEnvSettingsSource(Settings, env_file=ENV_EXAMPLE)
    return {name.upper(): value for name, value in source.env_vars.items()}


def test_el_env_example_documenta_todas_las_variables_de_la_configuracion() -> None:
    variables = {name.upper() for name in Settings.model_fields}

    assert set(variables_del_env_example()) == variables


def test_los_valores_del_env_example_son_una_configuracion_valida() -> None:
    settings = Settings(_env_file=ENV_EXAMPLE)

    assert settings.port == 8000
    assert settings.database_name == "document_store"


def test_el_env_example_no_incluye_credenciales_de_mongodb() -> None:
    database_url = variables_del_env_example()["DATABASE_URL"] or ""

    assert "@" not in database_url
