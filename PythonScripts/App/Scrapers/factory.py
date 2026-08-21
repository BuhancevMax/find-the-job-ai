from App.Scrapers.base import BaseScraper
from App.Scrapers.djinni import DjinniScraper
from App.Scrapers.workua import WorkUaScraper


class ScraperFactory:
    """Returns the scraper implementation for a platform."""

    _scrapers: dict[str, BaseScraper] = {
        "djinni": DjinniScraper(),
        "workua": WorkUaScraper(),
    }

    @classmethod
    def get_scraper(cls, platform: str) -> BaseScraper:
        platform_key = platform.strip().lower()

        try:
            return cls._scrapers[platform_key]
        except KeyError as exc:
            supported = ", ".join(sorted(cls._scrapers))
            raise ValueError(
                f"Платформа '{platform}' не поддерживается. "
                f"Доступные платформы: {supported}"
            ) from exc
