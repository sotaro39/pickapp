"""Fetcher services package"""

from app.services.fetcher.base import ArticleData, BaseFetcher
from app.services.fetcher.rss_fetcher import RSSFetcher
from app.services.fetcher.scraper import WebScraper

__all__ = ["ArticleData", "BaseFetcher", "RSSFetcher", "WebScraper"]
