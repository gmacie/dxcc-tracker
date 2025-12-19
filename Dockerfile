FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app
#ENV FLET_FORCE_WEB=1

RUN apt-get update && apt-get install -y \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

EXPOSE 8550 8551

#CMD ["python", "-m", "app.main"]
#CMD ["flet", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8550", "--web"]

# ✅ Run YOUR app, not the flet CLI

#CMD ["python", "app/main.py"]  comment out when changing to fastapi for uploads

CMD ["python", "-m", "app.server"]