from pathlib import Path
import json

from scraper.items import AuctionItem

class SaveMetaPipeline:
    def open_spider(self, spider):
        data_html_dir = spider.settings.get("DATA_EXPORT_DIR") / str(spider.category_id)
        self.out_dir = Path(data_html_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def process_item(self, item, spider):

        if not isinstance(item, AuctionItem):
            return item
        
        spider.logger.info("SaveHtmlPipeline: przetwarzanie item ID=%s", item.get("auction_id"))
        
        auction_id = item["auction_id"]
        

        dec=auction_id//1000
        temp_out_dir = Path(self.out_dir / f"{dec}000")

        temp_out_dir.mkdir(parents=True, exist_ok=True)

        data = dict(item)
        data.pop("main_content", None)

        out_path = temp_out_dir / f"{auction_id}.json"

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        

        return item
