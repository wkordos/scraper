from processor.celery_app import app


@app.task(name="task.etl.aukcjeKomornicze.grunty.process_item")
def process_item(item: dict) -> None:
    print("Odebrano item:")
    print(item)

    # tutaj Twoje ETL:
    # walidacja / transformacja / zapis do DB / dalsze taski