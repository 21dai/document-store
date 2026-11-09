"""main.py arranca uvicorn con lo que dice Settings, sin valores fijos."""

from unittest.mock import patch

import main
from app.config import Settings


def test_main_pasa_host_puerto_reload_y_apagado_ordenado_a_uvicorn() -> None:
    settings = Settings(
        _env_file=None,
        host="127.0.0.1",
        port=9000,
        debug=True,
        graceful_shutdown_seconds=7,
    )

    with (
        patch.object(main, "get_settings", return_value=settings),
        patch.object(main.uvicorn, "run") as run,
    ):
        main.main()

    run.assert_called_once_with(
        "app.main:app",
        host="127.0.0.1",
        port=9000,
        reload=True,
        timeout_graceful_shutdown=7,
    )
