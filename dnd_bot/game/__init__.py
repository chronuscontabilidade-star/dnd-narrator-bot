"""Núcleo determinístico das regras do jogo.

A IA pode interpretar e narrar ações, mas as regras mecânicas devem ser
resolvidas por este pacote.
"""

from .character import Character
from .combat import AttackResult, CombatState, Combatant, InitiativeResult
from .dice import DiceRoll, roll, roll_d20
from .engine import GameEngine
from .rules import (
    ability_modifier,
    ability_check,
    saving_throw,
    proficiency_bonus,
)

__all__ = [
    "AttackResult",
    "Character",
    "CombatState",
    "Combatant",
    "DiceRoll",
    "GameEngine",
    "InitiativeResult",
    "ability_check",
    "ability_modifier",
    "proficiency_bonus",
    "roll",
    "roll_d20",
    "saving_throw",
]
