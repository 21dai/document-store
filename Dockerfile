FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instalar dependencias primero para aprovechar la cache de capas
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-install-project --no-dev

# Copiar el código fuente y completar la instalación
COPY app ./app
COPY main.py ./
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
