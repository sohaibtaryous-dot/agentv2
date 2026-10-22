# -*- coding: utf-8 -*-
"""Appel LLM (Anthropic) avec sortie structurée forcée (tool use) : le modèle renvoie toujours un JSON conforme au schéma."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Callable

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"]


class LLMError(Exception):
    pass


class LLM:
    """`cfg` : ai_engine.AIConfig (clé + modèle). `fn` : fonction de remplacement (tests / hors ligne) :
    fn(system, user, schema, tool_name) -> dict."""

    def __init__(self, cfg=None, fn: Callable | None = None, gemini_key: str = "", gemini_model: str = GEMINI_MODELS[0], gemini_base: str = ""):
        self.cfg, self.fn = cfg, fn
        self.gemini_key, self.gemini_model = (gemini_key or "").strip(), gemini_model or GEMINI_MODELS[0]
        self.gemini_base = gemini_base or os.environ.get("GEMINI_BASE_URL", "") or GEMINI_URL

    @property
    def available(self) -> bool:
        return self.fn is not None or bool(self.gemini_key) or bool(self.cfg and getattr(self.cfg, "api_key", ""))

    @property
    def label(self) -> str:
        return f"Gemini · {self.gemini_model}" if self.gemini_key else "Claude"

    def _gemini(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        """Gemini (clé gratuite Google AI Studio) via l'API REST : JSON forcé (responseMimeType) + schéma dans la consigne."""
        body = {"systemInstruction": {"parts": [{"text": system + "\n\nRéponds UNIQUEMENT par un objet JSON valide, conforme à ce schéma JSON "
                                                 "(aucun texte autour, aucune balise) :\n" + json.dumps(schema, ensure_ascii=False)}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2, "maxOutputTokens": max_tokens}}
        req = urllib.request.Request(self.gemini_base.format(model=self.gemini_model), data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": self.gemini_key})
        last = ""
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")[:300]
                if exc.code in (429, 500, 503) and attempt < 2:             # quota / surcharge : nouvel essai après une pause
                    time.sleep(3 * (attempt + 1))
                    last = f"HTTP {exc.code}"
                    continue
                msg = {400: "Requête ou clé refusée par Gemini (vérifiez la clé).", 401: "Clé Gemini invalide.", 403: "Clé Gemini refusée (API non activée ?).",
                       404: f"Modèle « {self.gemini_model} » introuvable : choisissez un autre modèle Gemini.", 429: "Quota gratuit Gemini atteint : réessayez dans une minute."
                       }.get(exc.code, f"Erreur Gemini (HTTP {exc.code}).")
                raise LLMError(f"{msg} {detail if exc.code not in (401, 403) else ''}".strip()) from exc
            except Exception as exc:  # noqa: BLE001
                raise LLMError(f"Connexion à Gemini impossible : {type(exc).__name__}: {exc}") from exc
        else:
            raise LLMError(f"Gemini indisponible ({last}).")
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:  # noqa: BLE001
            reason = (data.get("promptFeedback") or {}).get("blockReason") or "réponse vide"
            raise LLMError(f"Gemini n'a pas répondu ({reason}).") from exc
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("Gemini a renvoyé un JSON invalide : reformulez ou réessayez.") from exc

    def structured(self, system: str, user: str, schema: dict, tool_name: str = "emit", max_tokens: int = 16000) -> dict:
        if self.fn is not None:
            return self.fn(system, user, schema, tool_name)
        if self.gemini_key:
            return self._gemini(system, user, schema, max_tokens)
        if not self.available:
            raise LLMError("Clé API manquante : renseignez une clé Gemini (gratuite) ou Anthropic.")
        import ai_engine
        client = ai_engine.make_client(self.cfg)
        kwargs = dict(model=self.cfg.model, max_tokens=max_tokens, system=system,
                      messages=[{"role": "user", "content": user}],
                      tools=[{"name": tool_name, "description": "Renvoie le résultat structuré.", "input_schema": schema}],
                      tool_choice={"type": "tool", "name": tool_name})
        try:
            with client.messages.stream(**kwargs) as stream:
                msg = stream.get_final_message()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(ai_engine.explain_error(exc) if hasattr(ai_engine, "explain_error") else str(exc)) from exc
        for block in msg.content:
            if getattr(block, "type", "") == "tool_use":
                data = block.input
                if isinstance(data, str):
                    data = json.loads(data)
                return data
        raise LLMError("Le modèle n'a renvoyé aucun résultat structuré.")
