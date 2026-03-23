"""
scheduler.py – Planificateur de tâches
Lance le bot automatiquement selon un planning configurable.

Usage :
  python scheduler.py                  → Lance selon le planning dans config.yaml
  python scheduler.py --now            → Lance immédiatement puis suit le planning
  python scheduler.py --interval 6h   → Lance toutes les 6h
"""

import asyncio
import subprocess
import sys
import time
import yaml
import click
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel

console = Console()


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_interval(interval_str: str) -> int:
    """Convertit '6h', '30m', '2h30m' en secondes."""
    total = 0
    import re
    hours   = re.search(r"(\d+)h", interval_str)
    minutes = re.search(r"(\d+)m", interval_str)
    if hours:
        total += int(hours.group(1)) * 3600
    if minutes:
        total += int(minutes.group(1)) * 60
    return total if total > 0 else 3600  # défaut : 1h


def run_bot(config_path: str, platform: str = None, dry_run: bool = False) -> bool:
    """Lance le bot dans un sous-processus."""
    cmd = [sys.executable, "main.py", "run", "--config", config_path]
    if platform:
        cmd += ["--platform", platform]
    if dry_run:
        cmd.append("--dry-run")

    console.print(f"\n[bold cyan]🚀 Lancement du bot – {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}[/]")

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        console.print(f"[red]❌ Erreur lancement : {e}[/]")
        return False


def format_next_run(next_run: datetime) -> str:
    delta = next_run - datetime.now()
    if delta.total_seconds() < 0:
        return "maintenant"
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    return f"dans {h}h {m:02d}m {s:02d}s"


@click.command()
@click.option("--config",    default="config.yaml", help="Fichier de configuration")
@click.option("--now",       is_flag=True,           help="Lancer immédiatement")
@click.option("--interval",  default=None,           help="Intervalle ex: 6h, 30m, 2h30m")
@click.option("--times",     default=None,           help="Heures fixes ex: '09:00,14:00,18:00'")
@click.option("--platform",  default=None,           help="Plateforme spécifique")
@click.option("--dry-run",   is_flag=True,           help="Mode simulation")
@click.option("--max-runs",  default=0,              help="Nombre max de lancements (0 = infini)")
def schedule(config, now, interval, times, platform, dry_run, max_runs):
    """
    Planificateur de candidatures automatiques.
    Lance le bot selon un planning régulier.
    """
    cfg = load_config(config)

    # Déterminer le mode de planification
    if interval:
        interval_sec = parse_interval(interval)
        mode = "interval"
    elif times:
        scheduled_times = [t.strip() for t in times.split(",")]
        mode = "fixed"
    else:
        # Valeurs par défaut depuis config
        interval_sec = 6 * 3600  # toutes les 6h
        mode = "interval"

    run_count = 0

    console.print(Panel(
        f"[bold cyan]⏰ SCHEDULER ACTIF[/]\n"
        f"[white]Mode : [yellow]{'Intervalle ' + interval if mode == 'interval' else 'Heures fixes : ' + times}[/]\n"
        f"Plateforme : [yellow]{platform or 'Toutes'}[/]\n"
        f"Max runs : [yellow]{'Infini' if max_runs == 0 else max_runs}[/][/]",
        title="Job Bot Scheduler",
        border_style="cyan"
    ))

    # Lancement immédiat si demandé
    if now:
        success = run_bot(config, platform, dry_run)
        run_count += 1
        _log_run(run_count, success)
        if max_runs > 0 and run_count >= max_runs:
            console.print("[green]✅ Nombre max de runs atteint.[/]")
            return

    try:
        while True:
            # Calculer le prochain lancement
            now_dt = datetime.now()

            if mode == "interval":
                next_run = datetime.now() + timedelta(seconds=interval_sec)

            elif mode == "fixed":
                next_run = _next_fixed_time(scheduled_times)

            # Afficher le countdown
            console.print(f"[dim]⏳ Prochain lancement : {format_next_run(next_run)} ({next_run.strftime('%H:%M:%S')})[/]")

            # Attendre
            _wait_until(next_run)

            # Lancer le bot
            success = run_bot(config, platform, dry_run)
            run_count += 1
            _log_run(run_count, success)

            if max_runs > 0 and run_count >= max_runs:
                console.print("[green]✅ Nombre max de runs atteint. Arrêt.[/]")
                break

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Scheduler arrêté manuellement.[/]")


def _next_fixed_time(times: list) -> datetime:
    """Retourne le prochain datetime correspondant à une heure fixe."""
    now = datetime.now()
    candidates = []
    for t in times:
        h, m = map(int, t.split(":"))
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        candidates.append(candidate)
    return min(candidates)


def _wait_until(target: datetime):
    """Attend jusqu'à une datetime cible, avec affichage de progression."""
    while datetime.now() < target:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            break
        time.sleep(min(30, remaining))  # vérifie toutes les 30s max


def _log_run(count: int, success: bool):
    status = "[green]✅ Succès[/]" if success else "[red]❌ Échec[/]"
    console.print(f"[dim]Run #{count} terminé – {status} – {datetime.now().strftime('%d/%m %H:%M')}[/]")


if __name__ == "__main__":
    schedule()
