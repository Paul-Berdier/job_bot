"""
utils/human_behavior.py – Simulation de comportement humain
Délais aléatoires, frappe simulée, mouvements de souris.
"""

import asyncio
import random
import math
from playwright.async_api import Page


async def random_delay(min_s: float = 1.0, max_s: float = 4.0):
    """Pause aléatoire pour imiter un humain."""
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


async def human_type(page: Page, selector: str, text: str, wpm: int = 60):
    """
    Frappe caractère par caractère avec des délais variables,
    comme un vrai utilisateur.
    """
    await page.click(selector)
    await random_delay(0.3, 0.8)

    chars_per_second = (wpm * 5) / 60  # 5 chars/mot en moyenne
    base_delay = 1.0 / chars_per_second

    for char in text:
        await page.type(selector, char, delay=0)
        # Variation humaine : parfois plus lent, parfois plus rapide
        jitter = random.gauss(0, base_delay * 0.3)
        delay_ms = max(30, int((base_delay + jitter) * 1000))
        await asyncio.sleep(delay_ms / 1000)

        # Pause occasionnelle (réfléchit ou relit)
        if random.random() < 0.05:
            await asyncio.sleep(random.uniform(0.5, 1.5))


async def human_click(page: Page, selector: str):
    """Clic avec un léger offset aléatoire dans l'élément."""
    element = await page.query_selector(selector)
    if not element:
        return
    box = await element.bounding_box()
    if not box:
        await page.click(selector)
        return

    x = box["x"] + box["width"]  * random.uniform(0.2, 0.8)
    y = box["y"] + box["height"] * random.uniform(0.2, 0.8)

    # Mouvement courbe vers la cible (Bézier simplifié)
    current = await page.evaluate("() => ({x: window.innerWidth/2, y: window.innerHeight/2})")
    steps = random.randint(8, 15)
    for i in range(steps):
        t = i / steps
        # Courbe de Bézier quadratique
        cx = current["x"] + (x - current["x"]) * t + random.gauss(0, 5)
        cy = current["y"] + (y - current["y"]) * t + random.gauss(0, 5)
        await page.mouse.move(cx, cy)
        await asyncio.sleep(random.uniform(0.01, 0.03))

    await page.mouse.move(x, y)
    await asyncio.sleep(random.uniform(0.05, 0.15))
    await page.mouse.click(x, y)


async def human_scroll(page: Page, direction: str = "down", amount: int = None):
    """Scroll humain avec variation."""
    if amount is None:
        amount = random.randint(200, 600)
    if direction == "up":
        amount = -amount

    # Scroll par petits incréments
    steps = random.randint(3, 8)
    per_step = amount // steps
    for _ in range(steps):
        await page.mouse.wheel(0, per_step)
        await asyncio.sleep(random.uniform(0.05, 0.2))


async def simulate_reading(page: Page, min_s: float = 2.0, max_s: float = 6.0):
    """Simule la lecture d'une page (scroll lent + pause)."""
    await random_delay(min_s * 0.3, max_s * 0.3)
    await human_scroll(page, "down", random.randint(100, 300))
    await random_delay(min_s * 0.4, max_s * 0.4)
    await human_scroll(page, "down", random.randint(100, 300))
    await random_delay(min_s * 0.3, max_s * 0.3)
