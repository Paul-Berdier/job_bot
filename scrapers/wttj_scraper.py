"""
scrapers/wttj_scraper.py – Scraper Welcome to the Jungle
"""

import hashlib
from typing import List, Optional
from playwright.async_api import Page, Browser
from scrapers.base_scraper import BaseScraper, JobOffer
from utils.human_behavior import random_delay, simulate_reading
from utils.logger import logger


class WTTJScraper(BaseScraper):
    PLATFORM_NAME = "wttj"
    BASE_URL      = "https://www.welcometothejungle.com"

    async def search_jobs(
        self,
        keywords: str,
        location: str,
        max_results: int = 20,
    ) -> List[JobOffer]:
        ctx  = await self.new_context()
        page = await ctx.new_page()
        jobs = []

        try:
            search_url = (
                f"{self.BASE_URL}/fr/jobs"
                f"?query={keywords.replace(' ', '%20')}"
                f"&refinementList%5Boffices.country_code%5D%5B%5D=FR"
            )
            logger.info(f"[WTTJ] Recherche : {keywords} | {location}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 5)

            # Gestion popup RGPD éventuelle
            try:
                gdpr_btn = await page.wait_for_selector(
                    "button[id*='accept'], button[class*='accept']",
                    timeout=4000
                )
                if gdpr_btn:
                    await gdpr_btn.click()
                    await random_delay(1, 2)
            except Exception:
                pass

            loaded = 0
            while len(jobs) < max_results:
                await simulate_reading(page)

                cards = await page.query_selector_all("li[data-testid='search-results-list-item-wrapper']")
                for card in cards[loaded:]:
                    if len(jobs) >= max_results:
                        break
                    job = await self._parse_card(card)
                    if job:
                        jobs.append(job)

                loaded = len(cards)

                # Scroll pour charger plus (infinite scroll)
                prev_count = len(jobs)
                await page.keyboard.press("End")
                await random_delay(2, 4)
                new_cards = await page.query_selector_all("li[data-testid='search-results-list-item-wrapper']")
                if len(new_cards) == loaded:
                    break  # Plus de résultats

        except Exception as e:
            logger.error(f"[WTTJ] Erreur recherche : {e}")
        finally:
            await ctx.close()

        logger.info(f"[WTTJ] {len(jobs)} offres trouvées")
        return jobs

    async def _parse_card(self, card) -> Optional[JobOffer]:
        try:
            title_el   = await card.query_selector("h4, [data-testid='job-title']")
            company_el = await card.query_selector("[data-testid='company-name'], span.sc-")
            location_el= await card.query_selector("span[data-testid='job-location']")
            link_el    = await card.query_selector("a")

            title   = (await title_el.inner_text()).strip()    if title_el    else "N/A"
            company = (await company_el.inner_text()).strip()  if company_el  else "N/A"
            loc     = (await location_el.inner_text()).strip() if location_el else ""
            href    = await link_el.get_attribute("href")      if link_el     else ""

            url = f"{self.BASE_URL}{href}" if href and not href.startswith("http") else href or ""
            job_id = hashlib.md5(url.encode()).hexdigest()[:16]

            return JobOffer(
                job_id=f"wttj_{job_id}",
                platform=self.PLATFORM_NAME,
                title=title,
                company=company,
                location=loc,
                url=url,
            )
        except Exception as e:
            logger.warning(f"[WTTJ] Erreur parsing card : {e}")
            return None

    async def get_job_details(self, page: Page, job: JobOffer) -> JobOffer:
        try:
            await page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(1, 3)
            await simulate_reading(page, 2, 5)

            desc_el = await page.query_selector(
                "div[data-testid='job-section-description'], "
                "section[data-testid='job-description']"
            )
            if desc_el:
                job.description = (await desc_el.inner_text()).strip()

            contract_el = await page.query_selector("[data-testid='job-contract-type']")
            if contract_el:
                job.contract_type = (await contract_el.inner_text()).strip()

            remote_el = await page.query_selector("[data-testid='remote']")
            if remote_el:
                job.remote = True

        except Exception as e:
            logger.warning(f"[WTTJ] Erreur détails offre : {e}")
        return job

    async def scrape_url(self, url: str) -> Optional[JobOffer]:
        ctx  = await self.new_context()
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(1, 3)

            job_id = hashlib.md5(url.encode()).hexdigest()[:16]

            title_el   = await page.query_selector("h1, [data-testid='job-title']")
            company_el = await page.query_selector("[data-testid='company-name']")
            loc_el     = await page.query_selector("[data-testid='job-location']")
            desc_el    = await page.query_selector("[data-testid='job-section-description']")

            job = JobOffer(
                job_id=f"wttj_{job_id}",
                platform=self.PLATFORM_NAME,
                title=(await title_el.inner_text()).strip() if title_el else "N/A",
                company=(await company_el.inner_text()).strip() if company_el else "N/A",
                location=(await loc_el.inner_text()).strip() if loc_el else "",
                url=url,
                description=(await desc_el.inner_text()).strip() if desc_el else "",
            )
            return job
        except Exception as e:
            logger.error(f"[WTTJ] Erreur scrape URL {url} : {e}")
            return None
        finally:
            await ctx.close()
