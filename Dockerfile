# syntax=docker/dockerfile:1

# --- Etapa 1: construir el entorno virtual con uv --------------------------
FROM python:3.14-slim AS builder

# Binario de uv con versión fija, solo en esta etapa: la imagen final no lo usa.
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv

# Bytecode precompilado (arranque más rápido) y copias reales en vez de links,
# para poder mover el .venv a la imagen final. Se usa el Python de la imagen.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Primero solo las dependencias: esta capa se reutiliza mientras no cambie
# uv.lock, aunque cambie el código.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app ./app
COPY main.py ./

# --- Etapa 2: imagen final, sin uv ni herramientas de build ---------------
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Usuario sin privilegios.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --from=builder --chown=appuser:appgroup /app /app

USER appuser

EXPOSE 8000

# /health solo dice que el proceso está vivo: no depende de MongoDB. La imagen
# slim no trae curl ni wget, así que se consulta con Python.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/health\", timeout=2)"]

# main.py lanza uvicorn con HOST y PORT de la configuración (variables de
# entorno), así que el puerto se puede cambiar sin tocar la imagen.
CMD ["python", "main.py"]
