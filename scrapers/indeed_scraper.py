"""
scrapers/indeed_scraper.py – Scraper Indeed France
"""

import re
import hashlib
from typing import List, Optional
from playwright.async_api import Page, Browser
from scrapers.base_scraper import BaseScraper, JobOffer
from utils.human_behavior import random_delay, human_scroll, simulate_reading
from utils.logger import logger


class IndeedScraper(BaseScraper):
    PLATFORM_NAME = "indeed"
    BASE_URL      = "https://fr.indeed.com"

    def __init__(self, config: dict, browser: Browser):
        super().__init__(config, browser)

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
                f"{self.BASE_URL}/jobs"
                f"?q={keywords.replace(' ', '+')}"
                f"&l={location.replace(' ', '+')}"
                f"&lang=fr"
            )
            logger.info(f"[Indeed] Recherche : {keywords} | {location}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)

            page_num = 0
            while len(jobs) < max_results:
                await simulate_reading(page)

                # Sélecteurs Indeed (à mettre à jour si le DOM change)
                cards = await page.query_selector_all("div.job_seen_beacon, div.jobsearch-SerpJobCard")

                for card in cards:
                    if len(jobs) >= max_results:
                        break
                    job = await self._parse_card(card)
                    if job:
                        jobs.append(job)

                # Pagination
                next_btn = await page.query_selector("a[data-testid='pagination-page-next'], a.np[aria-label='Suivant']")
                if not next_btn or len(jobs) >= max_results:
                    break

                await random_delay(2, 5)
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                page_num += 1

        except Exception as e:
            logger.error(f"[Indeed] Erreur recherche : {e}")
        finally:
            await ctx.close()

        logger.info(f"[Indeed] {len(jobs)} offres trouvées")
        return jobs

    async def _parse_card(self, card) -> Optional[JobOffer]:
        try:
            title_el   = await card.query_selector("h2.jobTitle span, .jobTitle a span")
            company_el = await card.query_selector("[data-testid='company-name'], .companyName")
            location_el= await card.query_selector("[data-testid='text-location'], .companyLocation")
            link_el    = await card.query_selector("h2.jobTitle a, .jobTitle a")

            title   = (await title_el.inner_text()).strip()   if title_el   else "N/A"
            company = (await company_el.inner_text()).strip() if company_el else "N/A"
            loc     = (await location_el.inner_text()).strip()if location_el else ""
            href    = await link_el.get_attribute("href")     if link_el    else ""

            url = f"{self.BASE_URL}{href}" if href and not href.startswith("http") else href or ""
            job_id = hashlib.md5(url.encode()).hexdigest()[:16]

            return JobOffer(
                job_id=f"indeed_{job_id}",
                platform=self.PLATFORM_NAME,
                title=title,
                company=company,
                location=loc,
                url=url,
            )
        except Exception as e:
            logger.warning(f"[Indeed] Erreur parsing card : {e}")
            return None

    async def get_job_details(self, page: Page, job: JobOffer) -> JobOffer:
        try:
            await page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(1, 3)
            await simulate_reading(page, 2, 5)

            desc_el = await page.query_selector("#jobDescriptionText, .jobsearch-jobDescriptionText")
            if desc_el:
                job.description = (await desc_el.inner_text()).strip()

            salary_el = await page.query_selector("[data-testid='attribute_snippet_testid'], .salary-snippet")
            if salary_el:
                job.salary = (await salary_el.inner_text()).strip()

            # Bouton postuler
            apply_btn = await page.query_selector("button#indeedApplyButton, a.indeed-apply-button")
            if apply_btn:
                job.application_url = job.url

        except Exception as e:
            logger.warning(f"[Indeed] Erreur détails offre : {e}")
        return job

    async def scrape_url(self, url: str) -> Optional[JobOffer]:
        ctx  = await self.new_context()
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(1, 3)

            job_id = hashlib.md5(url.encode()).hexdigest()[:16]
            title_el   = await page.query_selector("h1.jobsearch-JobInfoHeader-title")
            company_el = await page.query_selector("[data-testid='inlineHeader-companyName'] a")
            loc_el     = await page.query_selector("[data-testid='job-location']")
            desc_el    = await page.query_selector("#jobDescriptionText")

            job = JobOffer(
                job_id=f"indeed_{job_id}",
                platform=self.PLATFORM_NAME,
                title=(await title_el.inner_text()).strip() if title_el else "N/A",
                company=(await company_el.inner_text()).strip() if company_el else "N/A",
                location=(await loc_el.inner_text()).strip() if loc_el else "",
                url=url,
                description=(await desc_el.inner_text()).strip() if desc_el else "",
            )
            return job
        except Exception as e:
            logger.error(f"[Indeed] Erreur scrape URL {url} : {e}")
            return None
        finally:
            await ctx.close()
