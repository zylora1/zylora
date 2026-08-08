FROM python:3.13.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv /opt/venv
WORKDIR /app
COPY dist/api/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl "uvicorn[standard]==0.52.1" && rm -f /tmp/*.whl

RUN useradd --create-home --uid 10001 zylora
USER zylora
EXPOSE 8000
CMD ["uvicorn", "zylora_api.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
