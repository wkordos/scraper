from pathlib import Path

from scraper.items import AuctionItem

class SaveHtmlPipeline:
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

        html = item.get("main_content") or ""
        out_path = temp_out_dir / f"{auction_id}.html"
        out_path.write_text(html, encoding="utf-8")

        return item
