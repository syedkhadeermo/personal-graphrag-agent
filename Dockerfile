FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

COPY app /app/app
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN mkdir -p \
        /app/data/jobs \
        /app/data/results \
        /app/data/state \
    && useradd \
        --create-home \
        --uid 10001 \
        appuser \
    && sed -i 's/\r$//' \
        /app/docker-entrypoint.sh \
    && chmod 755 \
        /app/docker-entrypoint.sh \
    && chown -R appuser:appuser \
        /app \
        /home/appuser

USER appuser

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]