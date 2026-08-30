from abc import ABC, abstractmethod
from App.models import Vacancy, JobCriteria


class BaseScraper(ABC):
    """Common interface for all job-site scrapers."""

    @abstractmethod
    def fetch_jobs(self, keyword: str, criteria: JobCriteria | None = None) -> list[Vacancy]:
        raise NotImplementedError
