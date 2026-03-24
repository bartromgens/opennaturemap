FROM python:3.12-slim AS tippecanoe-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libsqlite3-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/felt/tippecanoe.git /tippecanoe \
    && cd /tippecanoe \
    && make -j \
    && make install


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=tippecanoe-builder /usr/local/bin/tippecanoe /usr/local/bin/tippecanoe

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY config/ config/
COPY manage.py .

RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
