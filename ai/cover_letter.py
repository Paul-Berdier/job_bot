"""
ai/cover_letter.py – Génération de lettres de motivation personnalisées
Supporte plusieurs providers IA :
  - openai   → ChatGPT (ton abonnement ou clé API)
  - groq     → Groq Cloud (GRATUIT, très rapide, llama3/mixtral)
  - ollama   → Ollama local (GRATUIT, tourne sur ton PC, aucune clé)
  - anthropic → Claude (si tu veux l'utiliser quand même)
"""

from tenacity import retry, stop_after_attempt, wait_exponential
from utils.logger import logger


SYSTEM_PROMPT = """Tu es un expert en recrutement et rédaction de lettres de motivation professionnelles.
Tu rédiges des lettres percutantes, personnalisées, concises (max 3 paragraphes) et sans formules creuses.
Tu analyses l'offre d'emploi pour identifier exactement ce que cherche le recruteur.
Tu rédiges en français, ton formel mais humain. Jamais de "Je me permets de vous contacter"."""

LETTER_TEMPLATE = """
Voici le profil du candidat :
{profile_summary}

Voici l'offre d'emploi :
Poste : {job_title}
Entreprise : {company}
Description : {job_description}

Génère une lettre de motivation en 3 paragraphes :
1. Accroche personnalisée qui montre que tu as lu l'offre
2. Pourquoi CE candidat est parfait pour CE poste (compétences clés + preuve concrète)
3. Enthousiasme pour l'entreprise + call-to-action simple

Format : texte brut, sans objet ni formule de politesse d'en-tête.
Commence directement par "Madame, Monsieur,"
"""

# ── Modèles recommandés par provider ──────────────────────────────────────────
DEFAULT_MODELS = {
    "openai":    "gpt-4o-mini",      # Rapide + pas cher (ou gpt-4o si tu veux le meilleur)
    "groq":      "llama3-70b-8192",  # Gratuit, excellents résultats
    "ollama":    "llama3",           # Gratuit local (ollama.com)
    "anthropic": "claude-haiku-4-5-20251001",  # Le plus rapide/économique de Claude
}


class CoverLetterGenerator:
    def __init__(self, provider: str, api_key: str, profile_summary: str, model: str = None):
        """
        provider        : "openai" | "groq" | "ollama" | "anthropic"
        api_key         : clé API (ignorée pour ollama)
        profile_summary : résumé de ton profil (utilisé dans le prompt)
        model           : forcer un modèle spécifique (optionnel)
        """
        self.provider        = provider.lower()
        self.api_key         = api_key
        self.profile_summary = profile_summary
        self.model           = model or DEFAULT_MODELS.get(self.provider, "gpt-4o-mini")
        self._client         = None
        self._init_client()

    def _init_client(self):
        """Initialise le client selon le provider."""
        if self.provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai non installé. Lance : pip install openai")

        elif self.provider == "groq":
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
            except ImportError:
                raise ImportError("groq non installé. Lance : pip install groq")

        elif self.provider == "ollama":
            # Ollama expose une API compatible OpenAI en local
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    base_url="http://localhost:11434/v1",
                    api_key="ollama",  # valeur bidon, obligatoire mais ignorée
                )
            except ImportError:
                raise ImportError("openai non installé. Lance : pip install openai")

        elif self.provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic non installé. Lance : pip install anthropic")

        else:
            raise ValueError(
                f"Provider '{self.provider}' non reconnu. "
                f"Choisir parmi : openai, groq, ollama, anthropic"
            )

        logger.info(f"🤖 Provider IA : {self.provider.upper()} | Modèle : {self.model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def generate(self, job_title: str, company: str, job_description: str) -> str:
        """
        Génère une lettre de motivation personnalisée.
        Retente automatiquement en cas d'erreur (max 3 fois).
        """
        prompt = LETTER_TEMPLATE.format(
            profile_summary=self.profile_summary,
            job_title=job_title,
            company=company,
            job_description=job_description[:3000],
        )

        logger.info(f"✍️  Génération lettre : {job_title} @ {company} [{self.provider}]...")

        if self.provider == "anthropic":
            return self._generate_anthropic(prompt)
        else:
            return self._generate_openai_compatible(prompt)

    def _generate_openai_compatible(self, prompt: str) -> str:
        """Appel unifié pour OpenAI, Groq et Ollama (même interface)."""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.7,
        )
        letter = response.choices[0].message.content.strip()
        logger.info("✅ Lettre générée avec succès")
        return letter

    def _generate_anthropic(self, prompt: str) -> str:
        """Appel API Anthropic (Claude)."""
        message = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        letter = message.content[0].text.strip()
        logger.info("✅ Lettre générée avec succès")
        return letter

    def generate_subject(self, job_title: str, company: str) -> str:
        """Génère un objet d'email professionnel."""
        return f"Candidature – {job_title} | {company}"
