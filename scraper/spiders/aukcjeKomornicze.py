import re
import scrapy
from scraper.dictionaries import CATEGORIES
from scraper.items import AuctionItem

class AukcjeKomorniczeSpider(scrapy.Spider):
    name = "aukcjeKomornicze"
    allowed_domains = ["licytacje.komornik.pl"]
    start_url = "https://licytacje.komornik.pl/Notice/Filter/"



    def __init__(self, category_id=None, **kwargs):
        super().__init__(**kwargs)

        if category_id is None:
            raise ValueError("Musisz podać argument -a category_id=<ID>")
        self.category_id = int(category_id)

        if self.category_id not in CATEGORIES:
            raise ValueError(
                f"Nieznana kategoria {self.category_id}. "
                f"Dostępne: {sorted(CATEGORIES.keys())}"
            )

        self.category_name = CATEGORIES[self.category_id]

        self.base_list_url = (
            f"{self.start_url}{self.category_id}"
        )

        self.logger.info(
            "Start spidera: category_id=%s (%s)",
            self.category_id,
            self.category_name,
        )

        self.details_regex = re.compile(r"/Notice/Details/(\d+)$")


    def start_requests(self):
            url = f"{self.base_list_url}"
            yield scrapy.Request(url, callback=self.parse_list, meta={"deltafetch_enabled": False})



    def parse_list(self, response):
        # zbierz linki do szczegółów aukcji
        detail_links = response.css(
            'a[href^="/Notice/Details/"]::attr(href)'
        ).getall()

        for href in detail_links:
            match = self.details_regex.match(href)
            if not match:
                continue

            auction_id = int(match.group(1))


            url = response.urljoin(href)

            self.logger.debug("Tworzenie requestu dla aukcji url=%s", url)

            yield scrapy.Request(
                url=url,
                callback=self.parse_detail,
                meta={
                    "auction_id": auction_id,
                    "category_id": self.category_id,
                    "deltafetch_key": str(auction_id),
                },
                dont_filter=True,
            )

        # obsługa paginacji – link „Następna >”
        next_page_href = response.xpath(
            '//a[contains(normalize-space(.), "Następna")]/@href'
        ).get()

        if next_page_href:
            yield response.follow(
                next_page_href,
                callback=self.parse_list,
                meta={"deltafetch_enabled": False},
            )

    def parse_detail(self, response):

        auction_id = int(response.meta["auction_id"])
        self.logger.info("Przetwarzanie aukcji ID=%s", auction_id)

        item = AuctionItem()

        preview_html = response.css(
        "div#main-content div#Preview"
        ).get()

        
        metadata = {}

        rows = response.css("div#main-content div.row")
        for row in rows:
            key = row.css("span.name *::text").getall()
            value = row.css("span.value *::text").getall()

            key = " ".join(t.strip() for t in key if t.strip())
            value = " ".join(t.strip() for t in value if t.strip())

            if key:
                metadata[key] = value
        yield AuctionItem(
            auction_id=auction_id,
            url=response.url,
            main_content=preview_html,
            metadata=metadata,
        )


