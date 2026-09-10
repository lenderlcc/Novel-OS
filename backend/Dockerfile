FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.30 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY novel_os ./novel_os
RUN uv sync --locked --no-dev --no-editable --no-python-downloads \
    && useradd --create-home --uid 10001 novel
COPY alembic.ini ./
COPY alembic ./alembic

USER novel
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "novel_os.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
