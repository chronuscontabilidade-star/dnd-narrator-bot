"""Núcleo determinístico das regras do jogo.

A IA pode interpretar e narrar ações, mas as regras mecânicas devem ser
resolvidas por este pacote.
"""

from .action import ActionIntent, ActionResolver, SKILLS
from .adventure import AdventureState
from .character import Character
from .combat import (
    ActionType,
    AttackResult,
    CombatState,
    Combatant,
    InitiativeResult,
    MoveResult,
    TurnState,
)
from .dice import DiceRoll, roll, roll_d20
from .engine import GameEngine
from .director import SceneDirector, SceneSuggestion
from .rules import (
    ability_modifier,
    ability_check,
    saving_throw,
    proficiency_bonus,
)

__all__ = [
    "ActionIntent",
    "ActionResolver",
    "ActionType",
    "AdventureState",
    "AttackResult",
    "Character",
    "CombatState",
    "Combatant",
    "DiceRoll",
    "GameEngine",
    "GoalDrivenPlayerAgent",
    "SceneDirector",
    "SceneSuggestion",
    "InitiativeResult",
    "MoveResult",
    "TurnState",
    "ability_check",
    "ability_modifier",
    "proficiency_bonus",
    "roll",
    "roll_d20",
    "saving_throw",
    "SKILLS",
]
