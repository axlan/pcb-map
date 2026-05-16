FROM python:3.12.1-alpine3.19

# Copy the uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY python/pyproject.toml python/uv.lock /app/python/

# Use uv's cache mount for fast, cached dependency installs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv --directory=python sync --frozen --no-install-project

COPY python /app/python
COPY scripts /app/scripts
COPY example_data /app/example_data

RUN --mount=type=cache,target=/root/.cache/uv \
    uv --directory=python sync --frozen

ENTRYPOINT ["/bin/sh", "-c", "source /app/python/.venv/bin/activate && exec \"$@\"", "--"]
CMD ["control-server", "display-shared-locations"]
