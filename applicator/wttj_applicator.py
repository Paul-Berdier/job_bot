"""
applicator/wttj_applicator.py – Candidature automatique sur Welcome to the Jungle
"""

import os
from playwright.async_api import Browser
from applicator.base_applicator import BaseApplicator
from scrapers.base_scraper import JobOffer
from utils.human_behavior import random_delay, human_type, human_click, simulate_reading
from utils.captcha_handler import check_for_captcha, handle_captcha
from utils.logger import logger


class WTTJApplicator(BaseApplicator):
    PLATFORM_NAME = "wttj"
    BASE_URL      = "https://www.welcometothejungle.com"
    LOGIN_URL     = "https://www.welcometothejungle.com/fr/signin"

    def __init__(self, config: dict, browser: Browser):
        super().__init__(config, browser)
        self.email    = config["platforms"]["wttj"]["email"]
        self.password = config["platforms"]["wttj"]["password"]
        self.cv_path  = os.path.abspath(config["profile"]["cv_path"])
        self.profile  = config["profile"]

    async def login(self) -> bool:
        if self._logged_in:
            return True
        try:
            self._context = await self.new_context()
            self._page    = await self._context.new_page()

            logger.info("[WTTJ] Connexion en cours...")
            await self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)

            # Accepter cookies si nécessaire
            try:
                cookie_btn = await self._page.wait_for_selector(
                    "button[data-gtm-name='accept-all-cookies'], #didomi-notice-agree-button",
                    timeout=4000
                )
                if cookie_btn:
                    await cookie_btn.click()
                    await random_delay(1, 2)
            except Exception:
                pass

            # Remplir email
            await human_type(self._page, "input[name='email'], input[type='email']", self.email)
            await random_delay(0.5, 1.5)

            # Remplir password
            await human_type(self._page, "input[name='password'], input[type='password']", self.password)
            await random_delay(0.5, 1)

            # Clic connexion
            await human_click(self._page, "button[type='submit']")
            await self._page.wait_for_load_state("networkidle", timeout=15000)
            await random_delay(2, 4)

            # Vérification CAPTCHA
            if await check_for_captcha(self._page):
                solved = await handle_captcha(self._page, "wttj")
                if not solved:
                    return False

            if "welcometothejungle.com/fr" in self._page.url and "signin" not in self._page.url:
                self._logged_in = True
                logger.info("[WTTJ] ✅ Connecté avec succès")
                return True
            else:
                logger.warning("[WTTJ] ⚠️ Échec connexion (vérification requise ?)")
                return False

        except Exception as e:
            logger.error(f"[WTTJ] Erreur connexion : {e}")
            await self._take_screenshot("login_error")
            return False

    async def apply(self, job: JobOffer, cover_letter: str) -> bool:
        if not self._logged_in:
            ok = await self.login()
            if not ok:
                return False

        try:
            logger.info(f"[WTTJ] Candidature → {job.title} @ {job.company}")
            await self._page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)
            await simulate_reading(self._page, 2, 5)

            # Bouton "Postuler"
            apply_btn_selector = (
                "a[data-testid='job-apply-button'], "
                "button[data-testid='job-apply-button'], "
                "a:has-text('Postuler'), button:has-text('Postuler')"
            )
            apply_btn = await self._page.wait_for_selector(apply_btn_selector, timeout=8000)

            if not apply_btn:
                logger.warning(f"[WTTJ] Bouton postuler introuvable pour {job.title}")
                return False

            await human_click(self._page, apply_btn_selector)
            await random_delay(2, 4)

            return await self._handle_apply_modal(job, cover_letter)

        except Exception as e:
            logger.error(f"[WTTJ] Erreur candidature {job.title} : {e}")
            await self._take_screenshot(f"apply_error_{job.job_id}")
            return False

    async def _handle_apply_modal(self, job: JobOffer, cover_letter: str) -> bool:
        """Gère la modale / page de candidature WTTJ."""
        await random_delay(1, 3)

        # Upload CV
        try:
            file_input = await self._page.wait_for_selector("input[type='file']", timeout=5000)
            if file_input:
                await file_input.set_input_files(self.cv_path)
                await random_delay(1, 2)
        except Exception:
            pass

        # Lettre de motivation
        try:
            cover_area = await self._page.wait_for_selector(
                "textarea[name*='cover'], textarea[placeholder*='lettre'], textarea[data-testid*='cover']",
                timeout=5000
            )
            if cover_area:
                await cover_area.click()
                await random_delay(0.5, 1)
                await self._page.fill(
                    "textarea[name*='cover'], textarea[placeholder*='lettre']",
                    cover_letter
                )
                await random_delay(1, 2)
        except Exception:
            pass

        # Remplir infos personnelles si demandé
        await self._fill_personal_info()

        # Soumettre
        submit_btn = await self._page.query_selector(
            "button[type='submit']:has-text('Envoyer'), "
            "button:has-text('Envoyer ma candidature'), "
            "button[data-testid='apply-submit']"
        )
        if submit_btn:
            await submit_btn.click()
            await random_delay(2, 4)

            # Vérification confirmation
            confirm = await self._page.query_selector(
                "[data-testid='application-success'], h2:has-text('candidature'), .success-message"
            )
            if confirm:
                logger.info(f"[WTTJ] ✅ Candidature envoyée : {job.title} @ {job.company}")
                return True

        logger.warning(f"[WTTJ] ⚠️ Candidature peut nécessiter une action manuelle")
        return False

    async def _fill_personal_info(self):
        """Remplit les champs basiques si présents."""
        fields = {
            "input[name='firstname'], input[placeholder*='prénom']": self.profile.get("first_name", ""),
            "input[name='lastname'], input[placeholder*='nom']":     self.profile.get("last_name", ""),
            "input[name='phone'], input[type='tel']":                self.profile.get("phone", ""),
        }
        for selector, value in fields.items():
            if not value:
                continue
            try:
                el = await self._page.query_selector(selector)
                if el:
                    current = await el.get_attribute("value") or ""
                    if not current:
                        await human_type(self._page, selector, value)
                        await random_delay(0.3, 0.8)
            except Exception:
                pass
