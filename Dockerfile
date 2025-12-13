FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y build-essential libsqlite3-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

FROM python:3.12-slim

RUN apt-get update && apt-get install -y libsqlite3-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy application files from builder
COPY --from=builder /app /app

# Ensure persistent DB directory exists
RUN mkdir -p /data

EXPOSE 8550

CMD ["python", "-m", "flet", "app/main.py", "--host=0.0.0.0", "--port=8550"]
