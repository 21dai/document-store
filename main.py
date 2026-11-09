"""Punto de entrada del servicio, en local y en Docker.

Local: `uv run python main.py`. Docker: la imagen arranca con
`CMD ["python", "main.py"]`.

Host, puerto, reload y el tiempo de apagado ordenado salen de la
configuración (`HOST`, `PORT`, `DEBUG`, `GRACEFUL_SHUTDOWN_SECONDS`), así que
se cambian con variables de entorno sin tocar el código ni la imagen.
"""

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=settings.graceful_shutdown_seconds,
    )


if __name__ == "__main__":
    main()
