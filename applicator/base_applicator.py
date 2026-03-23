"""
applicator/base_applicator.py – Classe abstraite pour postuler sur chaque plateforme
"""

from abc import ABC, abstractmethod
from playwright.async_api import Browser, BrowserContext
from fake_useragent import UserAgent
from scrapers.base_scraper import JobOffer


class BaseApplicator(ABC):
    PLATFORM_NAME: str = "base"

    def __init__(self, config: dict, browser: Browser):
        self.config   = config
        self.browser  = browser
        self.ua       = UserAgent()
        self._context = None
        self._page    = None
        self._logged_in = False

    async def new_context(self) -> BrowserContext:
        return await self.browser.new_context(
            user_agent=self.ua.chrome,
            viewport={"width": 1366, "height": 768},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            accept_downloads=True,
        )

    @abstractmethod
    async def login(self) -> bool:
        """Se connecte à la plateforme. Retourne True si succès."""
        ...

    @abstractmethod
    async def apply(self, job: JobOffer, cover_letter: str) -> bool:
        """
        Postule à une offre avec le CV + lettre de motivation générée.
        Retourne True si la candidature a été envoyée avec succès.
        """
        ...

    async def close(self):
        if self._context:
            await self._context.close()

    async def _take_screenshot(self, name: str):
        """Capture d'écran en cas d'erreur (si activé dans la config)."""
        if self.config.get("bot", {}).get("screenshot_on_error") and self._page:
            import os
            from datetime import datetime
            path = f"logs/screenshot_{self.PLATFORM_NAME}_{name}_{datetime.now().strftime('%H%M%S')}.png"
            os.makedirs("logs", exist_ok=True)
            await self._page.screenshot(path=path)
