"""
dashboard.py – Tableau de bord temps réel des candidatures
Affiche les stats, les dernières candidatures et les lettres générées.

Usage : python dashboard.py
"""

import os
import sys
import time
import yaml
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.align import Align
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(__file__))
from utils.db import Application, Base

console = Console()
DB_PATH = os.path.join("data", "applications.db")


def get_session():
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def render_stats(session) -> Panel:
    total   = session.query(Application).count()
    applied = session.query(Application).filter_by(status="applied").count()
    errors  = session.query(Application).filter_by(status="error").count()
    dry     = session.query(Application).filter_by(status="dry_run").count()

    # Stats par plateforme
    platforms = session.query(
        Application.platform,
        func.count(Application.id)
    ).group_by(Application.platform).all()

    plat_str = "  ".join(
        f"[cyan]{p}[/] [white]{c}[/]" for p, c in platforms
    ) or "[dim]Aucune donnée[/]"

    # Candidatures cette semaine
    week_ago = datetime.utcnow() - timedelta(days=7)
    this_week = session.query(Application).filter(
        Application.applied_at >= week_ago,
        Application.status == "applied"
    ).count()

    content = (
        f"[bold green]✅ Envoyées : {applied}[/]    "
        f"[bold red]❌ Erreurs : {errors}[/]    "
        f"[bold blue]📊 Total : {total}[/]    "
        f"[bold yellow]🔬 Dry-run : {dry}[/]\n\n"
        f"[dim]Cette semaine : [white]{this_week}[/]    "
        f"Par plateforme : {plat_str}[/]"
    )
    return Panel(content, title="📈 Statistiques globales", border_style="green")


def render_recent_table(session, limit: int = 15) -> Table:
    recent = (
        session.query(Application)
        .order_by(Application.applied_at.desc())
        .limit(limit)
        .all()
    )

    table = Table(
        title=f"📋 {limit} dernières candidatures",
        border_style="blue",
        show_lines=True,
    )
    table.add_column("Date",        style="dim",    width=12)
    table.add_column("Plateforme",  style="cyan",   width=12)
    table.add_column("Poste",       style="bold",   width=35)
    table.add_column("Entreprise",  style="yellow", width=25)
    table.add_column("Statut",                      width=10)

    status_styles = {
        "applied": "[bold green]✅ envoyé[/]",
        "error":   "[bold red]❌ erreur[/]",
        "dry_run": "[bold blue]🔵 test[/]",
        "skipped": "[dim]⏭️ passé[/]",
    }

    for app in recent:
        table.add_row(
            app.applied_at.strftime("%d/%m %H:%M"),
            app.platform,
            (app.job_title or "–")[:35],
            (app.company   or "–")[:25],
            status_styles.get(app.status, app.status),
        )

    if not recent:
        table.add_row("[dim]–[/]", "[dim]–[/]", "[dim]Aucune candidature encore[/]", "[dim]–[/]", "[dim]–[/]")

    return table


def render_last_letter(session) -> Panel:
    """Affiche la dernière lettre de motivation générée."""
    last = (
        session.query(Application)
        .filter(Application.cover_letter.isnot(None))
        .filter(Application.cover_letter != "")
        .order_by(Application.applied_at.desc())
        .first()
    )
    if not last:
        return Panel("[dim]Aucune lettre générée pour l'instant.[/]", title="📝 Dernière lettre IA")

    preview = (last.cover_letter or "")[:500]
    if len(last.cover_letter) > 500:
        preview += "\n[dim]...(tronqué)[/]"

    return Panel(
        f"[bold]{last.job_title}[/] @ [yellow]{last.company}[/]  [dim]({last.platform} – {last.applied_at.strftime('%d/%m %H:%M')})[/]\n\n"
        f"[white]{preview}[/]",
        title="📝 Dernière lettre de motivation IA",
        border_style="magenta",
    )


def render_daily_chart(session) -> Panel:
    """Mini graphe ASCII des candidatures par jour (7 derniers jours)."""
    days = []
    for i in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        count = session.query(Application).filter(
            func.date(Application.applied_at) == day.isoformat(),
            Application.status == "applied"
        ).count()
        days.append((day, count))

    max_count = max((c for _, c in days), default=1) or 1
    bar_width  = 20

    lines = []
    for day, count in days:
        bar_len = int((count / max_count) * bar_width)
        bar     = "█" * bar_len + "░" * (bar_width - bar_len)
        label   = day.strftime("%a %d")
        lines.append(f"[dim]{label}[/] [cyan]{bar}[/] [white]{count}[/]")

    return Panel(
        "\n".join(lines),
        title="📅 Candidatures / jour (7j)",
        border_style="cyan",
    )


def show_dashboard(live_refresh: bool = True, refresh_rate: int = 10):
    """Affiche le tableau de bord, avec ou sans rafraîchissement automatique."""
    if not os.path.exists(DB_PATH):
        console.print("[yellow]⚠️ Aucune base de données trouvée. Lancez d'abord le bot.[/]")
        return

    def render():
        session = get_session()
        try:
            rows = [
                render_stats(session),
                Columns([render_daily_chart(session), render_last_letter(session)]),
                render_recent_table(session),
                Panel(
                    "[dim]Ctrl+C pour quitter · Rafraîchissement auto toutes les 10s[/]",
                    border_style="dim"
                ),
            ]
            return "\n".join(str(r) for r in rows)
        finally:
            session.close()

    console.print(Panel.fit(
        "[bold cyan]📊 JOB BOT DASHBOARD[/]",
        border_style="cyan"
    ))

    if not live_refresh:
        session = get_session()
        console.print(render_stats(session))
        console.print(render_daily_chart(session))
        console.print(render_recent_table(session))
        console.print(render_last_letter(session))
        session.close()
        return

    try:
        with Live(console=console, refresh_per_second=0.1, screen=False) as live:
            while True:
                session = get_session()
                layout = Layout()

                stats_panel  = render_stats(session)
                chart_panel  = render_daily_chart(session)
                letter_panel = render_last_letter(session)
                table        = render_recent_table(session)
                session.close()

                console.clear()
                console.print(Panel.fit("[bold cyan]📊 JOB BOT DASHBOARD[/] [dim]– Ctrl+C pour quitter[/]", border_style="cyan"))
                console.print(stats_panel)
                console.print(Columns([chart_panel, letter_panel]))
                console.print(table)

                time.sleep(refresh_rate)
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard fermé.[/]")


if __name__ == "__main__":
    import click

    @click.command()
    @click.option("--no-live", is_flag=True, help="Afficher une fois sans rafraîchissement")
    @click.option("--refresh", default=10, help="Intervalle de rafraîchissement en secondes")
    def main(no_live, refresh):
        """📊 Tableau de bord des candidatures Job Bot."""
        show_dashboard(live_refresh=not no_live, refresh_rate=refresh)

    main()
