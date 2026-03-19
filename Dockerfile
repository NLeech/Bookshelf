# syntax=docker/dockerfile:1

ARG workdir=Bookshelf
ARG user=bookshelf

# build stage
FROM python:3.12-slim as builder

ARG workdir

WORKDIR /$workdir

ENV PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gcc libc-dev libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# install uv
COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /uvx /bin/

# get and build packages
COPY pyproject.toml uv.lock .python-version ./
# uv sync creates a .venv automatically and installs dependencies
# without trying to install the missing project source code
# --no-dev ensures testing/linting tools aren't compiled into the production image
RUN uv sync --frozen --no-dev --no-install-project

# final stage
FROM python:3.12-slim

ARG workdir
ARG user

RUN adduser --disabled-password --gecos '' --no-create-home --shell /bin/false $user

WORKDIR /$workdir

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual environment
COPY --from=builder /$workdir/.venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1

COPY --chown=$user:$user . .

RUN chmod +x start.sh

EXPOSE 8080

USER $user

CMD ["./start.sh"]

