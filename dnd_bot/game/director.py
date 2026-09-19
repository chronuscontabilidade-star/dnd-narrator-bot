"""Diretor de Cena para manter o ritmo narrativo sem controlar o jogador.

O Diretor não resolve regras e não escolhe ações pelos jogadores. Ele observa
o estado persistente e decide apenas se existe motivo para oferecer uma
oportunidade narrativa ou uma sugestão.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .adventure import AdventureState


DirectorLevel = Literal["none", "opportunity", "suggestion", "intervention"]


@dataclass(frozen=True)
class SceneSuggestion:
    level: DirectorLevel
    reason: str
    actions: tuple[str, ...] = ()


class SceneDirector:
    """Detecta estagnação e objetivos relevantes sem forçar soluções."""

    def __init__(self, *, idle_steps: int = 3):
        if idle_steps < 1:
            raise ValueError("idle_steps deve ser positivo.")
        self.idle_steps = idle_steps

    def evaluate(
        self,
        state: AdventureState,
        *,
        recent_steps: int = 0,
        progress_since_last_scene: bool = True,
    ) -> SceneSuggestion:
        if progress_since_last_scene:
            return SceneSuggestion(
                level="none",
                reason="Os jogadores estão produzindo progresso.",
            )

        if recent_steps < self.idle_steps:
            return SceneSuggestion(
                level="opportunity",
                reason="A cena pode oferecer um detalhe relevante sem interromper a liberdade.",
            )

        quest = self._active_quest(state)
        if quest:
            actions = self._suggestions_for_current_location(state)
            return SceneSuggestion(
                level="suggestion",
                reason=f"A cena está parada enquanto a quest '{quest.get('titulo')}' permanece ativa.",
                actions=actions,
            )

        return SceneSuggestion(
            level="intervention",
            reason="A cena está parada e não há objetivo ativo claramente disponível.",
        )

    def _active_quest(self, state: AdventureState) -> dict | None:
        for quest in state.data.get("quests", []):
            if quest.get("status") == "ativa":
                return quest
        return None

    def _suggestions_for_current_location(self, state: AdventureState) -> tuple[str, ...]:
        current_id = state.data.get("progresso", {}).get("local_atual")
        current = next(
            (loc for loc in state.data.get("locais", []) if loc.get("id") == current_id),
            None,
        )
        if not current:
            return (
                "Observar o ambiente",
                "Conversar com alguém",
                "Investigar a área",
            )

        suggestions: list[str] = [
            "Observar o ambiente",
            "Investigar a área",
        ]

        npc_here = any(
            npc.get("local_atual") == current_id and npc.get("vivo", True)
            for npc in state.data.get("npcs", [])
        )
        if npc_here:
            suggestions.append("Conversar com alguém")

        connections = current.get("conexoes", [])
        for location_id in connections:
            location = next(
                (loc for loc in state.data.get("locais", []) if loc.get("id") == location_id),
                None,
            )
            if location and location.get("descoberto"):
                suggestions.append(f"Ir para {location.get('nome')}")

        return tuple(dict.fromkeys(suggestions))[:4]


__all__ = ["SceneDirector", "SceneSuggestion"]
