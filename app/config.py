from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación, cargada desde variables de entorno.

    Las variables se pueden definir en un archivo `.env` en la raíz del
    proyecto. Ver `.env.example` para la lista completa.
    """

    app_name: str = "document-store"
    app_version: str = "0.1.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    api_v1_prefix: str = "/api/v1"

    # Conexión a MongoDB. El timeout (en milisegundos) se aplica a la
    # conexión y a la selección del servidor: si MongoDB no responde, las
    # operaciones fallan en ese tiempo en lugar de quedar colgadas.
    database_url: str = "mongodb://localhost:27017"
    database_name: str = "document_store"
    database_timeout_ms: int = 3000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
