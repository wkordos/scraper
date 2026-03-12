FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# instalacja zależności
COPY processor/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# kopiowanie kodu processor
COPY processor ./processor

# katalog na logi
RUN mkdir -p /app/logs

# domyślna zmienna środowiskowa
ENV RABBITMQ_HOST=rabbitmq

# kontener ma pozostać uruchomiony
CMD ["tail", "-f", "/dev/null"]