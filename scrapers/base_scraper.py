"""
scrapers/base_scraper.py – Classe abstraite commune à tous les scrapers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from playwright.async_api import Browser, BrowserContext, Page
from fake_useragent import UserAgent


@dataclass
class JobOffer:
    """Représente une offre d'emploi scrapée."""
    job_id:          str
    platform:        str
    title:           str
    company:         str
    location:        str
    url:             str
    description:     str  = ""
    salary:          str  = ""
    contract_type:   str  = ""
    remote:          bool = False
    posted_date:     str  = ""
    application_url: str  = ""


class BaseScraper(ABC):
    PLATFORM_NAME: str = "base"

    def __init__(self, config: dict, browser: Browser):
        self.config  = config
        self.browser = browser
        self.ua      = UserAgent()

    async def new_context(self) -> BrowserContext:
        """Crée un contexte navigateur avec un User-Agent réaliste."""
        return await self.browser.new_context(
            user_agent=self.ua.chrome,
            viewport={"width": 1366, "height": 768},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            java_script_enabled=True,
            accept_downloads=True,
        )

    @abstractmethod
    async def search_jobs(
        self,
        keywords: str,
        location: str,
        max_results: int = 20,
    ) -> List[JobOffer]:
        """Recherche des offres d'emploi par mots-clés et localisation."""
        ...

    @abstractmethod
    async def get_job_details(self, page: Page, job: JobOffer) -> JobOffer:
        """Récupère le détail complet d'une offre (description, salaire, etc.)."""
        ...

    @abstractmethod
    async def scrape_url(self, url: str) -> Optional[JobOffer]:
        """Scrape une offre à partir d'une URL directe."""
        ...

    def _passes_filters(self, job: JobOffer, filters: dict) -> bool:
        """Applique les filtres de config (mots exclus, salaire min, etc.)."""
        title_lower = job.title.lower()
        desc_lower  = job.description.lower()

        for kw in filters.get("skip_keywords", []):
            if kw.lower() in title_lower or kw.lower() in desc_lower:
                return False

        return True
