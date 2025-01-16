import base64
from dataclasses import dataclass
from typing import Any, Self, override

from crawl4ai import CacheMode, CrawlerRunConfig
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.async_webcrawler import AsyncWebCrawler
from playwright.async_api import Page
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.http.response import Response
from scrapy.spiders import Spider


@dataclass
class BasicAuth:
    username: str
    password: str


class BasicAuthSpider(Spider):
    name = "basic_auth_spider"
    allowed_domains = ["testpages.eviltester.com"]
    start_urls = [
        "https://testpages.eviltester.com/styled/auth/basic-auth-results.html"
    ]

    def __init__(self, authentication: BasicAuth, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http_user = authentication.username
        self.http_pass = authentication.password
        self.http_auth_domain = self.allowed_domains[0]

        # Set up the crawler strategy with authentication
        async def on_page_context_created(page: Page, **kwargs):
            credentials = base64.b64encode(
                f"{self.http_user}:{self.http_pass}".encode()
            ).decode()
            await page.set_extra_http_headers({"Authorization": f"Basic {credentials}"})

        self.crawler_strategy = AsyncPlaywrightCrawlerStrategy(verbose=True)
        self.crawler_strategy.set_hook(
            "on_page_context_created", on_page_context_created
        )
        self.crawl4ai_crawler = AsyncWebCrawler(
            verbose=True, crawler_strategy=self.crawler_strategy
        )

    @override
    @classmethod
    def from_crawler(cls, crawler: Crawler, *args, **kwargs) -> Self:
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_opened, signals.spider_opened)
        crawler.signals.connect(spider.spider_closed, signals.spider_closed)
        return spider

    async def spider_opened(self) -> None:
        """Initialize crawler when spider starts"""
        await self.crawl4ai_crawler.start()

    @override
    async def parse(self, response: Response) -> dict[str, Any]:
        crawl_result = await self.crawl4ai_crawler.arun(
            url=response.url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                exclude_external_links=True,
                exclude_social_media_links=True,
                verbose=True,
            ),
        )

        return {"markdown": crawl_result.markdown}

    async def spider_closed(self) -> None:
        """Clean up crawler when spider finishes"""
        await self.crawl4ai_crawler.close()


if __name__ == "__main__":
    from scrapy.crawler import CrawlerProcess

    crawler_process = CrawlerProcess(
        settings={
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        }
    )
    crawler_process.crawl(
        BasicAuthSpider,
        BasicAuth(username="authorized", password="password001"),
    )
    crawler_process.start()
