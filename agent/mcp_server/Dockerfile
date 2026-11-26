FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /srv

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# Instalación de dependencias (capa cacheable): solo el manifiesto primero.
COPY pyproject.toml ./
RUN poetry install --no-root --only main --no-interaction

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
