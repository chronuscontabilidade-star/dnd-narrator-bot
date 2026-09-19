"""Orquestrador mecânico mínimo do jogo."""

from __future__ import annotations

from .character import Character
from .rules import CheckResult, ability_check, saving_throw


class GameEngine:
    """Ponto de entrada para regras determinísticas.

    A camada de bot/IA deverá pedir ao engine para resolver regras, em vez
    de calcular resultados por conta própria.
    """

    def ability_check(
        self,
        character: Character,
        ability: str,
        dc: int,
        *,
        advantage: bool = False,
        disadvantage: bool = False,
        rng=None,
    ) -> CheckResult:
        return ability_check(
            character.abilities[ability],
            dc,
            proficiency=ability in character.proficient_abilities,
            level=character.level,
            advantage=advantage,
            disadvantage=disadvantage,
            rng=rng,
        )

    def saving_throw(
        self,
        character: Character,
        ability: str,
        dc: int,
        *,
        advantage: bool = False,
        disadvantage: bool = False,
        rng=None,
    ) -> CheckResult:
        return saving_throw(
            character.abilities[ability],
            dc,
            proficiency=ability in character.proficient_abilities,
            level=character.level,
            advantage=advantage,
            disadvantage=disadvantage,
            rng=rng,
        )
