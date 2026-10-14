"""Entrypoint de conveniencia para desarrollo local.

Uso: `uv run python main.py`

En producción o con Docker se recomienda invocar uvicorn directamente:
`uvicorn app.main:app --host 0.0.0.0 --port 8000`
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
    )


if __name__ == "__main__":
    main()
