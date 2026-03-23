"""
applicator/indeed_applicator.py – Candidature automatique sur Indeed
"""

import os
from playwright.async_api import Browser
from applicator.base_applicator import BaseApplicator
from scrapers.base_scraper import JobOffer
from utils.human_behavior import random_delay, human_type, human_click, simulate_reading
from utils.captcha_handler import check_for_captcha, handle_captcha
from utils.logger import logger


class IndeedApplicator(BaseApplicator):
    PLATFORM_NAME = "indeed"
    BASE_URL      = "https://fr.indeed.com"
    LOGIN_URL     = "https://secure.indeed.com/auth"

    def __init__(self, config: dict, browser: Browser):
        super().__init__(config, browser)
        self.email    = config["platforms"]["indeed"]["email"]
        self.password = config["platforms"]["indeed"]["password"]
        self.cv_path  = os.path.abspath(config["profile"]["cv_path"])

    async def login(self) -> bool:
        if self._logged_in:
            return True
        try:
            self._context = await self.new_context()
            self._page    = await self._context.new_page()

            logger.info("[Indeed] Connexion en cours...")
            await self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)

            # Email
            email_input = await self._page.wait_for_selector(
                "input[name='__email'], input[type='email']", timeout=10000
            )
            await human_type(self._page, "input[name='__email'], input[type='email']", self.email)
            await random_delay(0.5, 1.5)

            await self._page.press("input[name='__email']", "Enter")
            await random_delay(1, 3)

            # Password
            pwd_input = await self._page.wait_for_selector(
                "input[name='__password'], input[type='password']", timeout=10000
            )
            await human_type(self._page, "input[type='password']", self.password)
            await random_delay(0.5, 1.5)
            await self._page.press("input[type='password']", "Enter")

            await self._page.wait_for_load_state("networkidle", timeout=15000)
            await random_delay(2, 4)

            # Vérification CAPTCHA
            if await check_for_captcha(self._page):
                solved = await handle_captcha(self._page, "indeed")
                if not solved:
                    return False

            # Vérification connexion
            if "myaccount" in self._page.url or "indeed.com/jobs" in self._page.url or "resume" in self._page.url:
                self._logged_in = True
                logger.info("[Indeed] ✅ Connecté avec succès")
                return True
            else:
                logger.warning("[Indeed] ⚠️ Connexion peut nécessiter une vérification manuelle (CAPTCHA ?)")
                return False

        except Exception as e:
            logger.error(f"[Indeed] Erreur connexion : {e}")
            await self._take_screenshot("login_error")
            return False

    async def apply(self, job: JobOffer, cover_letter: str) -> bool:
        if not self._logged_in:
            ok = await self.login()
            if not ok:
                return False

        try:
            logger.info(f"[Indeed] Candidature → {job.title} @ {job.company}")
            await self._page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)
            await simulate_reading(self._page, 2, 4)

            # Chercher le bouton "Postuler maintenant" / "Indeed Apply"
            apply_btn = await self._page.query_selector(
                "button#indeedApplyButton, "
                "button[data-testid='indeedApplyButton'], "
                "a.indeed-apply-button"
            )

            if not apply_btn:
                logger.warning(f"[Indeed] Pas de bouton postuler trouvé pour {job.title}")
                return False

            await human_click(self._page, "button#indeedApplyButton, button[data-testid='indeedApplyButton'], a.indeed-apply-button")
            await random_delay(2, 4)

            # Gérer le flux Indeed Apply (multi-étapes)
            return await self._handle_apply_flow(job, cover_letter)

        except Exception as e:
            logger.error(f"[Indeed] Erreur candidature {job.title} : {e}")
            await self._take_screenshot(f"apply_error_{job.job_id}")
            return False

    async def _handle_apply_flow(self, job: JobOffer, cover_letter: str) -> bool:
        """Navigue dans le formulaire multi-étapes d'Indeed Apply."""
        max_steps = 8
        step = 0

        while step < max_steps:
            await random_delay(1, 3)
            step += 1

            page_content = await self._page.content()

            # Upload CV
            if await self._page.query_selector("input[type='file']"):
                file_input = await self._page.query_selector("input[type='file']")
                await file_input.set_input_files(self.cv_path)
                await random_delay(1, 2)

            # Lettre de motivation
            cover_letter_area = await self._page.query_selector(
                "textarea[name='coverletter'], textarea[id*='cover'], textarea[placeholder*='lettre']"
            )
            if cover_letter_area:
                await cover_letter_area.click()
                await random_delay(0.5, 1)
                await self._page.fill("textarea[name='coverletter']", cover_letter)
                await random_delay(1, 2)

            # Bouton Continuer / Suivant
            next_btn = await self._page.query_selector(
                "button[data-testid='continue-button'], "
                "button[type='submit']:not([data-testid='close-button'])"
            )

            if next_btn:
                btn_text = (await next_btn.inner_text()).lower()
                await human_click(self._page, "button[data-testid='continue-button'], button[type='submit']:not([data-testid='close-button'])")
                await random_delay(2, 4)

                # Si c'est le bouton final "Envoyer" / "Soumettre"
                if any(w in btn_text for w in ["envoyer", "soumettre", "submit", "postuler"]):
                    logger.info(f"[Indeed] ✅ Candidature envoyée : {job.title} @ {job.company}")
                    return True

            # Vérification si candidature confirmée
            confirm = await self._page.query_selector(
                "[data-testid='confirmation-page'], .ia-PostApply, h1:has-text('envoyée')"
            )
            if confirm:
                logger.info(f"[Indeed] ✅ Candidature confirmée : {job.title} @ {job.company}")
                return True

        logger.warning(f"[Indeed] ⚠️ Formulaire non complété après {max_steps} étapes")
        return False
