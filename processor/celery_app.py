from celery import Celery
from kombu import Queue

BROKER_URL = "amqp://scraper:scraper@localhost:5672//"

app = Celery("processor", broker=BROKER_URL)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # nie twórz brakujących kolejek automatycznie
    task_create_missing_queues=False,

    # domyślna kolejka dla tego taska
    task_default_queue="aukcjeKomornicze",

    # consumer-only: kolejka istnieje już w RabbitMQ
    task_queues=(
        Queue(
            "aukcjeKomornicze",
            no_declare=True,
        ),
    ),

    task_routes={
        "task.etl.aukcjeKomornicze.grunty.process_item": {
            "queue": "aukcjeKomornicze",
        }
    },
)

import processor.tasks