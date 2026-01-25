import scrapy

class AuctionItem(scrapy.Item):
    auction_id = scrapy.Field()
    url = scrapy.Field()
    metadata = scrapy.Field()
    main_content = scrapy.Field()
