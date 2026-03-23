"""
utils/captcha_handler.py – Détection et gestion des CAPTCHAs
Quand un CAPTCHA est détecté, le bot se met en pause et attend
que l'utilisateur le résolve manuellement dans la fenêtre du navigateur.
"""

import asyncio
from playwright.async_api import Page
from utils.logger import logger
from rich.console import Console
from rich.panel import Panel

console = Console()

# Sélecteurs connus de CAPTCHAs
CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "div.g-recaptcha",
    "div[class*='captcha']",
    "#captcha",
    "input[name='captcha']",
    "img[alt*='captcha' i]",
]

# Indicateurs dans l'URL
CAPTCHA_URL_PATTERNS = [
    "captcha",
    "challenge",
    "verify",
    "robot",
    "human",
]

# Textes dans la page
CAPTCHA_TEXT_PATTERNS = [
    "je ne suis pas un robot",
    "i'm not a robot",
    "prouvez que vous êtes humain",
    "vérification de sécurité",
    "security check",
    "verifying you are human",
    "unusual traffic",
    "trafic inhabituel",
]


async def check_for_captcha(page: Page) -> bool:
    """Vérifie si la page contient un CAPTCHA. Retourne True si détecté."""
    # Vérifier l'URL
    current_url = page.url.lower()
    for pattern in CAPTCHA_URL_PATTERNS:
        if pattern in current_url:
            return True

    # Vérifier les sélecteurs DOM
    for selector in CAPTCHA_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                return True
        except Exception:
            pass

    # Vérifier le contenu textuel
    try:
        body_text = (await page.inner_text("body")).lower()
        for pattern in CAPTCHA_TEXT_PATTERNS:
            if pattern in body_text:
                return True
    except Exception:
        pass

    return False


async def handle_captcha(page: Page, platform: str, timeout_seconds: int = 120) -> bool:
    """
    Gère un CAPTCHA détecté.
    Met le bot en pause et attend que l'utilisateur le résolve.
    Retourne True si résolu dans le délai imparti.
    """
    logger.warning(f"🚨 [{platform}] CAPTCHA détecté !")

    console.print(Panel(
        f"[bold yellow]⚠️  CAPTCHA DÉTECTÉ sur {platform.upper()}[/]\n\n"
        f"[white]Le bot a été mis en pause.[/]\n"
        f"[cyan]→ Résolvez le CAPTCHA manuellement dans la fenêtre du navigateur[/]\n"
        f"[dim]Timeout : {timeout_seconds} secondes[/]",
        title="🤖 Action requise",
        border_style="yellow"
    ))

    # Attendre la résolution (vérifie toutes les 3 secondes)
    for elapsed in range(0, timeout_seconds, 3):
        await asyncio.sleep(3)

        still_captcha = await check_for_captcha(page)
        if not still_captcha:
            logger.info(f"✅ [{platform}] CAPTCHA résolu ! Reprise dans 2 secondes...")
            await asyncio.sleep(2)
            return True

        remaining = timeout_seconds - elapsed - 3
        if elapsed % 15 == 0 and elapsed > 0:
            console.print(f"[yellow]⏳ En attente du CAPTCHA... ({remaining}s restantes)[/]")

    logger.error(f"❌ [{platform}] Timeout : CAPTCHA non résolu après {timeout_seconds}s")
    return False


async def safe_goto(page: Page, url: str, platform: str, **kwargs) -> bool:
    """
    Navigation sécurisée : va sur une URL et vérifie immédiatement
    si un CAPTCHA est apparu.
    """
    try:
        await page.goto(url, **kwargs)
        await asyncio.sleep(1)

        if await check_for_captcha(page):
            return await handle_captcha(page, platform)

        return True
    except Exception as e:
        logger.error(f"[{platform}] Erreur navigation vers {url} : {e}")
        return False
