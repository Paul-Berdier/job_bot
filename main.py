"""
main.py – Point d'entrée du Job Bot
Usage :
  python main.py run                        → Recherche + candidature auto
  python main.py apply --url <URL>          → Candidature sur une URL directe
  python main.py stats                      → Afficher les statistiques
  python main.py config                     → Vérifier la configuration
"""

import asyncio
import os
import sys
import yaml
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from playwright.async_api import async_playwright

from utils.logger import logger
from utils.db import Database
from ai.cover_letter import CoverLetterGenerator

from scrapers.indeed_scraper   import IndeedScraper
from scrapers.wttj_scraper     import WTTJScraper
from scrapers.hellowork_scraper import HelloWorkScraper

from applicator.indeed_applicator    import IndeedApplicator
from applicator.wttj_applicator      import WTTJApplicator
from applicator.hellowork_applicator import HelloWorkApplicator

console = Console()

SCRAPERS    = {"indeed": IndeedScraper,    "wttj": WTTJScraper,    "hellowork": HelloWorkScraper}
APPLICATORS = {"indeed": IndeedApplicator, "wttj": WTTJApplicator, "hellowork": HelloWorkApplicator}


def load_config(path: str = "config.yaml") -> dict:
    if not os.path.exists(path):
        console.print(f"[red]❌ config.yaml introuvable. Copiez config.yaml et remplissez-le.[/red]")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─── CLI ──────────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """🤖 Job Bot – Candidatures automatiques avec IA"""
    pass


@cli.command()
@click.option("--config", default="config.yaml", help="Chemin du fichier config")
@click.option("--dry-run", is_flag=True, help="Simuler sans postuler réellement")
@click.option("--platform", default=None, help="Limiter à une plateforme (indeed/wttj/hellowork)")
def run(config, dry_run, platform):
    """Lance la recherche et les candidatures automatiques."""
    cfg = load_config(config)
    _print_banner()
    asyncio.run(_run_bot(cfg, dry_run=dry_run, platform_filter=platform))


@cli.command()
@click.argument("url")
@click.option("--config", default="config.yaml", help="Chemin du fichier config")
def apply(url, config):
    """Postule à une offre depuis son URL directement."""
    cfg = load_config(config)
    _print_banner()
    asyncio.run(_apply_single_url(cfg, url))


@cli.command()
@click.option("--config", default="config.yaml", help="Chemin du fichier config")
def stats(config):
    """Affiche les statistiques des candidatures."""
    load_config(config)
    db = Database()
    s  = db.get_stats()
    recent = db.get_recent(10)
    db.close()

    console.print(Panel(
        f"[bold green]✅ Envoyées : {s['applied']}[/]  "
        f"[bold red]❌ Erreurs : {s['errors']}[/]  "
        f"[bold blue]📊 Total : {s['total']}[/]",
        title="📈 Statistiques Job Bot"
    ))

    if recent:
        table = Table(title="10 dernières candidatures")
        table.add_column("Date",      style="dim")
        table.add_column("Plateforme", style="cyan")
        table.add_column("Poste",      style="bold white")
        table.add_column("Entreprise", style="yellow")
        table.add_column("Statut",     style="green")

        for app in recent:
            status_color = "green" if app.status == "applied" else "red"
            table.add_row(
                app.applied_at.strftime("%d/%m %H:%M"),
                app.platform,
                app.job_title[:40],
                app.company[:30],
                f"[{status_color}]{app.status}[/]",
            )
        console.print(table)


@cli.command("config")
@click.option("--config", default="config.yaml", help="Chemin du fichier config")
def check_config(config):
    """Vérifie que la configuration est valide."""
    cfg = load_config(config)

    checks = [
        ("Clé API Anthropic",   bool(cfg.get("anthropic_api_key", "").startswith("sk-ant"))),
        ("CV présent",          os.path.exists(cfg["profile"]["cv_path"])),
        ("Mots-clés définis",   bool(cfg["search"]["keywords"])),
        ("Email Indeed",        bool(cfg["platforms"]["indeed"]["email"])),
        ("Email WTTJ",          bool(cfg["platforms"]["wttj"]["email"])),
        ("Email HelloWork",     bool(cfg["platforms"]["hellowork"]["email"])),
    ]

    table = Table(title="Configuration")
    table.add_column("Paramètre")
    table.add_column("Statut")
    for name, ok in checks:
        table.add_row(name, "✅" if ok else "❌")
    console.print(table)


# ─── Logique principale ───────────────────────────────────────────────────────

async def _run_bot(cfg: dict, dry_run: bool = False, platform_filter: str = None):
    db  = Database()
    ai_cfg = cfg.get("ai", {})
    gen = CoverLetterGenerator(
        provider=ai_cfg.get("provider", "groq"),
        api_key=ai_cfg.get("api_key", ""),
        profile_summary=cfg["profile_summary"],
        model=ai_cfg.get("model") or None,
    )

    search_cfg  = cfg["search"]
    filters     = cfg.get("filters", {})
    max_jobs    = search_cfg["max_jobs_per_run"]
    headless    = cfg["bot"]["headless"]
    min_d       = cfg["bot"]["min_delay_seconds"]
    max_d       = cfg["bot"]["max_delay_seconds"]

    applied_count = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ]
        )

        for platform_name, ScraperClass in SCRAPERS.items():
            if platform_filter and platform_filter != platform_name:
                continue
            if not cfg["platforms"][platform_name]["enabled"]:
                continue

            logger.info(f"\n{'='*50}")
            logger.info(f"🔍 Plateforme : {platform_name.upper()}")

            scraper    = ScraperClass(cfg, browser)
            applicator = APPLICATORS[platform_name](cfg, browser) if not dry_run else None

            # Connexion
            if applicator:
                logged_in = await applicator.login()
                if not logged_in:
                    logger.warning(f"⚠️ Connexion {platform_name} échouée, passage à la suivante")
                    continue

            # Recherche par mots-clés
            all_jobs = []
            for keyword in search_cfg["keywords"]:
                jobs = await scraper.search_jobs(
                    keywords=keyword,
                    location=search_cfg["location"],
                    max_results=max_jobs,
                )
                all_jobs.extend(jobs)

            # Déduplication + filtrage
            seen = set()
            jobs_to_process = []
            for job in all_jobs:
                if job.job_id in seen:
                    continue
                seen.add(job.job_id)
                if filters.get("skip_if_already_applied") and db.already_applied(job.job_id):
                    logger.info(f"⏭️ Déjà postulé : {job.title}")
                    continue
                if not scraper._passes_filters(job, filters):
                    logger.info(f"⏭️ Filtré : {job.title}")
                    continue
                jobs_to_process.append(job)

            logger.info(f"📋 {len(jobs_to_process)} offres à traiter sur {platform_name}")

            # Traitement
            ctx_page = await browser.new_page()
            for job in jobs_to_process:
                if applied_count >= max_jobs:
                    break

                # Récupérer les détails
                job = await scraper.get_job_details(ctx_page, job)

                # Générer la lettre de motivation
                cover_letter = gen.generate(
                    job_title=job.title,
                    company=job.company,
                    job_description=job.description,
                )

                if dry_run:
                    console.print(Panel(
                        f"[bold]{job.title}[/] @ [yellow]{job.company}[/]\n\n{cover_letter[:300]}...",
                        title=f"[DRY RUN] {platform_name}"
                    ))
                    db.save_application(
                        job_id=job.job_id, platform=platform_name,
                        job_title=job.title, company=job.company,
                        job_url=job.url, cover_letter=cover_letter,
                        status="dry_run",
                    )
                    applied_count += 1
                    continue

                # Postuler
                success = await applicator.apply(job, cover_letter)
                status  = "applied" if success else "error"

                db.save_application(
                    job_id=job.job_id, platform=platform_name,
                    job_title=job.title, company=job.company,
                    job_url=job.url, cover_letter=cover_letter,
                    status=status,
                )

                if success:
                    applied_count += 1
                    console.print(f"[bold green]✅ [{applied_count}/{max_jobs}] {job.title} @ {job.company}[/]")

                # Délai entre candidatures
                import random
                await asyncio.sleep(random.uniform(min_d, max_d))

            await ctx_page.close()
            if applicator:
                await applicator.close()

        await browser.close()

    console.print(f"\n[bold green]🎉 Session terminée : {applied_count} candidature(s) envoyée(s)[/]")
    db.close()


async def _apply_single_url(cfg: dict, url: str):
    """Postule à une seule offre depuis son URL."""
    db  = Database()
    ai_cfg = cfg.get("ai", {})
    gen = CoverLetterGenerator(
        provider=ai_cfg.get("provider", "groq"),
        api_key=ai_cfg.get("api_key", ""),
        profile_summary=cfg["profile_summary"],
        model=ai_cfg.get("model") or None,
    )

    # Détecter la plateforme depuis l'URL
    platform = None
    if "indeed" in url:
        platform = "indeed"
    elif "welcometothejungle" in url:
        platform = "wttj"
    elif "hellowork" in url:
        platform = "hellowork"
    else:
        console.print("[red]❌ URL non reconnue. Plateformes supportées : Indeed, WTTJ, HelloWork[/red]")
        return

    if db.already_applied(f"{platform}_{hash(url)}"):
        console.print("[yellow]⚠️ Déjà postulé à cette offre.[/yellow]")
        db.close()
        return

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=cfg["bot"]["headless"],
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        ScraperClass    = SCRAPERS[platform]
        ApplicatorClass = APPLICATORS[platform]

        scraper    = ScraperClass(cfg, browser)
        applicator = ApplicatorClass(cfg, browser)

        job = await scraper.scrape_url(url)
        if not job:
            console.print("[red]❌ Impossible de récupérer les détails de l'offre.[/red]")
            await browser.close()
            return

        console.print(f"[bold]📄 Offre détectée :[/] {job.title} @ {job.company}")

        cover_letter = gen.generate(
            job_title=job.title,
            company=job.company,
            job_description=job.description,
        )

        console.print(Panel(cover_letter, title="📝 Lettre de motivation générée"))

        logged_in = await applicator.login()
        if not logged_in:
            console.print("[red]❌ Connexion échouée.[/red]")
            await browser.close()
            return

        success = await applicator.apply(job, cover_letter)

        db.save_application(
            job_id=job.job_id, platform=platform,
            job_title=job.title, company=job.company,
            job_url=url, cover_letter=cover_letter,
            status="applied" if success else "error",
        )

        if success:
            console.print(f"[bold green]✅ Candidature envoyée avec succès ![/]")
        else:
            console.print(f"[bold red]❌ Candidature échouée. Vérifiez les logs.[/]")

        await applicator.close()
        await browser.close()

    db.close()


def _print_banner():
    console.print(Panel.fit(
        "[bold cyan]🤖 JOB BOT[/]\n"
        "[dim]Candidatures automatiques avec IA • Indeed | WTTJ | HelloWork[/]",
        border_style="cyan"
    ))


# Init packages
for pkg in ["scrapers", "applicator", "ai", "utils"]:
    init = os.path.join(pkg, "__init__.py")
    if not os.path.exists(init):
        open(init, "w").close()

if __name__ == "__main__":
    cli()
