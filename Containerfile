# syntax=docker/dockerfile:1.4
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim as base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

#================================================================
# BUILDER
#
# Installs build dependencies, and installs all dependencies, including
# dev dependencies, into a virtual environment.
#================================================================
FROM base as builder

# Install build dependencies.
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential

# Install poetry
RUN pip install poetry

# Copy the project files into the builder.
COPY pyproject.toml poetry.lock ./

# Install dependencies into a virtual environment.
RUN poetry install --no-root

#================================================================
# TESTER
#
# Runs unit tests.
#================================================================
FROM builder as tester

# Copy the application files into the tester.
COPY . .

# Run tests.
RUN poetry run pytest

#================================================================
# FINAL
#
# Creates the final, lean production image.
#================================================================
FROM base as final

ARG APP_NAME

# Copy the virtual environment from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Activate the virtual environment.
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application files into the final image.
COPY . .

# Use the non-privileged user to run the application.
USER appuser

# Set the entrypoint to the application.
CMD ["python", "-m", "APP_NAME.main"]
