"""
scrapers/hellowork_scraper.py – Scraper HelloWork
"""

import hashlib
from typing import List, Optional
from playwright.async_api import Page, Browser
from scrapers.base_scraper import BaseScraper, JobOffer
from utils.human_behavior import random_delay, simulate_reading
from utils.logger import logger


class HelloWorkScraper(BaseScraper):
    PLATFORM_NAME = "hellowork"
    BASE_URL      = "https://www.hellowork.com"

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
                f"{self.BASE_URL}/fr-fr/emploi/recherche.html"
                f"?k={keywords.replace(' ', '+')}"
                f"&l={location.replace(' ', '+')}"
            )
            logger.info(f"[HelloWork] Recherche : {keywords} | {location}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)

            # Accepter cookies si présent
            try:
                cookie_btn = await page.wait_for_selector(
                    "button#didomi-notice-agree-button, button[data-testid='cookie-accept']",
                    timeout=4000
                )
                if cookie_btn:
                    await cookie_btn.click()
                    await random_delay(1, 2)
            except Exception:
                pass

            page_num = 1
            while len(jobs) < max_results:
                await simulate_reading(page)

                cards = await page.query_selector_all("li[data-type='job-item'], article.job-item")
                for card in cards:
                    if len(jobs) >= max_results:
                        break
                    job = await self._parse_card(card)
                    if job:
                        jobs.append(job)

                # Pagination
                next_btn = await page.query_selector(
                    "a[aria-label='Suivant'], a.pagination__next, [data-testid='pagination-next']"
                )
                if not next_btn or len(jobs) >= max_results:
                    break

                await random_delay(2, 5)
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                page_num += 1

        except Exception as e:
            logger.error(f"[HelloWork] Erreur recherche : {e}")
        finally:
            await ctx.close()

        logger.info(f"[HelloWork] {len(jobs)} offres trouvées")
        return jobs

    async def _parse_card(self, card) -> Optional[JobOffer]:
        try:
            title_el   = await card.query_selector("a.job-title, h3.tw-typo-l a, [data-testid='job-title']")
            company_el = await card.query_selector(".job-company, [data-testid='company-name']")
            location_el= await card.query_selector(".job-location, [data-testid='job-location']")
            link_el    = await card.query_selector("a.job-title, h3 a")

            title   = (await title_el.inner_text()).strip()    if title_el    else "N/A"
            company = (await company_el.inner_text()).strip()  if company_el  else "N/A"
            loc     = (await location_el.inner_text()).strip() if location_el else ""
            href    = await link_el.get_attribute("href")      if link_el     else ""

            url = f"{self.BASE_URL}{href}" if href and not href.startswith("http") else href or ""
            job_id = hashlib.md5(url.encode()).hexdigest()[:16]

            return JobOffer(
                job_id=f"hw_{job_id}",
                platform=self.PLATFORM_NAME,
                title=title,
                company=company,
                location=loc,
                url=url,
            )
        except Exception as e:
            logger.warning(f"[HelloWork] Erreur parsing card : {e}")
            return None

    async def get_job_details(self, page: Page, job: JobOffer) -> JobOffer:
        try:
            await page.goto(job.url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(1, 3)
            await simulate_reading(page, 2, 5)

            desc_el = await page.query_selector(
                ".job-description, [data-testid='job-description'], #job-detail-description"
            )
            if desc_el:
                job.description = (await desc_el.inner_text()).strip()

            salary_el = await page.query_selector(".job-salary, [data-testid='salary']")
            if salary_el:
                job.salary = (await salary_el.inner_text()).strip()

            contract_el = await page.query_selector(".job-contract, [data-testid='contract-type']")
            if contract_el:
                job.contract_type = (await contract_el.inner_text()).strip()

        except Exception as e:
            logger.warning(f"[HelloWork] Erreur détails offre : {e}")
        return job

    async def scrape_url(self, url: str) -> Optional[JobOffer]:
        ctx  = await self.new_context()
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await random_delay(1, 3)

            job_id = hashlib.md5(url.encode()).hexdigest()[:16]

            title_el   = await page.query_selector("h1")
            company_el = await page.query_selector(".job-company, [data-testid='company-name']")
            loc_el     = await page.query_selector(".job-location, [data-testid='job-location']")
            desc_el    = await page.query_selector(".job-description, #job-detail-description")

            job = JobOffer(
                job_id=f"hw_{job_id}",
                platform=self.PLATFORM_NAME,
                title=(await title_el.inner_text()).strip() if title_el else "N/A",
                company=(await company_el.inner_text()).strip() if company_el else "N/A",
                location=(await loc_el.inner_text()).strip() if loc_el else "",
                url=url,
                description=(await desc_el.inner_text()).strip() if desc_el else "",
            )
            return job
        except Exception as e:
            logger.error(f"[HelloWork] Erreur scrape URL {url} : {e}")
            return None
        finally:
            await ctx.close()
