# Stage 1: budowanie frontendu
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Najpierw kopiujemy pliki package dla pamięci podręcznej Dockera
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install --silent

# Kopiujemy źródła frontendu i budujemy
COPY frontend/ ./
RUN npm run build

# Stage 2: obraz docelowy
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# Instalacja zależności wymaganych przez serwer
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        curl \
        tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y gcc && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Kopiowanie kodu backendu
COPY app ./app
COPY core ./core
COPY util ./util
COPY main.py .
COPY VERSION .

# Kopiowanie zbudowanych plików statycznych frontendu
COPY --from=frontend-builder /app/static ./static

# Katalog danych tworzony przy starcie
RUN mkdir -p ./data

VOLUME ["/app/data"]
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["python", "-u", "main.py"]
