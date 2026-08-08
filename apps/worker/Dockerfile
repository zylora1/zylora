FROM python:3.13.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv /opt/venv
WORKDIR /app
COPY dist/worker/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

RUN useradd --create-home --uid 10001 zylora
USER zylora
CMD ["celery", "-A", "zylora_worker.celery_app:celery_app", "worker", "--loglevel=INFO"]
