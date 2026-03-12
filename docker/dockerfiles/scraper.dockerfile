FROM python:3.12-slim

# zmienne dla python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# katalog roboczy
WORKDIR /app

# kopiujemy requirements osobno (lepszy cache builda)
COPY scraper/requirements.txt .

# instalujemy zależności
RUN pip install --no-cache-dir -r requirements.txt

# kopiujemy kod scrapera
COPY scraper ./scraper
COPY scrapy.cfg .

# utworzenie katalogów na dane i logi
RUN mkdir -p \
    /app/data \
    /app/data/db \
    /app/data/exports \
    /app/logs

# opcjonalnie prawa zapisu
RUN chmod -R 777 /app/data /app/logs

# kontener ma się nie zamykać
CMD ["tail", "-f", "/dev/null"]