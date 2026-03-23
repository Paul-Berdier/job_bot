"""
applicator/hellowork_applicator.py – Candidature automatique sur HelloWork
"""

import os
from playwright.async_api import Browser
from applicator.base_applicator import BaseApplicator
from scrapers.base_scraper import JobOffer
from utils.human_behavior import random_delay, human_type, human_click, simulate_reading
from utils.captcha_handler import check_for_captcha, handle_captcha
from utils.logger import logger


class HelloWorkApplicator(BaseApplicator):
    PLATFORM_NAME = "hellowork"
    BASE_URL      = "https://www.hellowork.com"
    LOGIN_URL     = "https://www.hellowork.com/fr-fr/compte/connexion.html"

    def __init__(self, config: dict, browser: Browser):
        super().__init__(config, browser)
        self.email    = config["platforms"]["hellowork"]["email"]
        self.password = config["platforms"]["hellowork"]["password"]
        self.cv_path  = os.path.abspath(config["profile"]["cv_path"])
        self.profile  = config["profile"]

    async def login(self) -> bool:
        if self._logged_in:
            return True
        try:
            self._context = await self.new_context()
            self._page    = await self._context.new_page()

            logger.info("[HelloWork] Connexion en cours...")
            await self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)

            # Accepter cookies
            try:
                cookie_btn = await self._page.wait_for_selector(
                    "button#didomi-notice-agree-button, button[aria-label*='Accepter']",
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

            # Connexion
            await human_click(self._page, "button[type='submit'], input[type='submit']")
            await self._page.wait_for_load_state("networkidle", timeout=15000)
            await random_delay(2, 4)

            # Vérification CAPTCHA
            if await check_for_captcha(self._page):
                solved = await handle_captcha(self._page, "hellowork")
                if not solved:
                    return False

            if "connexion" not in self._page.url and "hellowork.com" in self._page.url:
                self._logged_in = True
                logger.info("[HelloWork] ✅ Connecté avec succès")
                return True
            else:
                logger.warning("[HelloWork] ⚠️ Échec connexion")
                return False

        except Exception as e:
            logger.error(f"[HelloWork] Erreur connexion : {e}")
            await self._take_screenshot("login_error")
            return False

    async def apply(self, job: JobOffer, cover_letter: str) -> bool:
        if not self._logged_in:
            ok = await self.login()
            if not ok:
                return False

        try:
            logger.info(f"[HelloWork] Candidature → {job.title} @ {job.company}")
            await self._page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)
            await simulate_reading(self._page, 2, 4)

            # Bouton "Postuler"
            apply_selector = (
                "a[data-gtm-label='apply'], "
                "button.apply-btn, "
                "a:has-text('Postuler'), "
                "button:has-text('Postuler à cette offre')"
            )
            apply_btn = await self._page.wait_for_selector(apply_selector, timeout=8000)

            if not apply_btn:
                logger.warning(f"[HelloWork] Bouton postuler introuvable pour {job.title}")
                return False

            await human_click(self._page, apply_selector)
            await random_delay(2, 4)

            return await self._handle_apply_form(job, cover_letter)

        except Exception as e:
            logger.error(f"[HelloWork] Erreur candidature {job.title} : {e}")
            await self._take_screenshot(f"apply_error_{job.job_id}")
            return False

    async def _handle_apply_form(self, job: JobOffer, cover_letter: str) -> bool:
        """Gère le formulaire HelloWork."""
        await random_delay(1, 3)

        # Upload CV
        try:
            file_input = await self._page.wait_for_selector(
                "input[type='file'][accept*='pdf'], input[type='file']",
                timeout=5000
            )
            if file_input:
                await file_input.set_input_files(self.cv_path)
                await random_delay(1, 2)
                logger.info("[HelloWork] CV uploadé")
        except Exception:
            pass

        # Lettre de motivation
        try:
            cover_area = await self._page.query_selector(
                "textarea[name*='cover'], textarea[name*='lettre'], textarea[placeholder*='motivation']"
            )
            if cover_area:
                await cover_area.fill(cover_letter)
                await random_delay(1, 2)
        except Exception:
            pass

        # Infos personnelles
        await self._fill_personal_info()

        # Soumettre
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Envoyer')",
            "button:has-text('Postuler')",
        ]
        for sel in submit_selectors:
            try:
                btn = await self._page.query_selector(sel)
                if btn and await btn.is_visible():
                    await human_click(self._page, sel)
                    await random_delay(2, 4)
                    break
            except Exception:
                continue

        # Confirmation
        confirm = await self._page.query_selector(
            ".confirmation, .success, h1:has-text('envoyée'), h2:has-text('succès')"
        )
        if confirm:
            logger.info(f"[HelloWork] ✅ Candidature envoyée : {job.title} @ {job.company}")
            return True

        # Vérifier URL de confirmation
        if "confirmation" in self._page.url or "merci" in self._page.url:
            logger.info(f"[HelloWork] ✅ Candidature confirmée via URL")
            return True

        logger.warning(f"[HelloWork] ⚠️ Statut candidature incertain pour {job.title}")
        return False

    async def _fill_personal_info(self):
        fields = {
            "input[name='firstname']": self.profile.get("first_name", ""),
            "input[name='lastname']":  self.profile.get("last_name", ""),
            "input[name='phone']":     self.profile.get("phone", ""),
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
