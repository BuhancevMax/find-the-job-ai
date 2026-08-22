from abc import ABC, abstractmethod
from App.models import Vacancy


class BaseScraper(ABC):
    """Common interface for all job-site scrapers."""

    @abstractmethod
    def fetch_jobs(self, keyword: str) -> list[Vacancy]:
        raise NotImplementedError
