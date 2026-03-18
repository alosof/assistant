FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY tools agent.py chainlit_app.py ./
COPY .chainlit .chainlit

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "chainlit", "run", "chainlit_app.py", "--host", "0.0.0.0", "--port", "8000"]
