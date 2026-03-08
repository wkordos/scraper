# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from celery import Celery

TASK_NAME = "task.etl.aukcjeKomornicze.grunty.process_item"
EXCHANGE = "scraper"
ROUTING_KEY = "aukcjeKomornicze.grunty.insert"


class SendToMiddlewarePipeline:

    def open_spider(self, spider):
        settings = spider.crawler.settings

        broker_url = settings.get("RABBITMQ_BROKER_URL")

        self.publisher_app = Celery("scrapy_producer", broker=broker_url)

        self.publisher_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
        )



    
    def process_item(self, item, spider):

        #payload = dict(item)
        payload = ItemAdapter(item).asdict()

        self.publisher_app.send_task(
            TASK_NAME,
            args=[payload],
            exchange=EXCHANGE,
            routing_key=ROUTING_KEY,
            delivery_mode=2,  # persistent message
            serializer="json",
        )


        return item
