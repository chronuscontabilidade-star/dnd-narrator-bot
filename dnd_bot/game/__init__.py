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
from .simulator import (
    CampaignSimulator,
    GoalDrivenPlayerAgent,
    PartyMember,
    PartySimulationResult,
    PersonalityPlayerAgent,
    PlayerAgent,
    ScriptedPlayerAgent,
    SimulationReport,
    SimulationResult,
    build_vertical_slice_adventure,
)
from .director import SceneDirector, SceneSuggestion
from .party import DecisionResolution, PartyDecision, PartyDecisionResolver, PartyVote
from .participation import PartyParticipation, PartyParticipationResolver, ParticipationResolution
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
    "CampaignSimulator",
    "GoalDrivenPlayerAgent",
    "PartyMember",
    "PartySimulationResult",
    "PersonalityPlayerAgent",
    "PlayerAgent",
    "ScriptedPlayerAgent",
    "SimulationReport",
    "SimulationResult",
    "build_vertical_slice_adventure",
    "SceneDirector",
    "SceneSuggestion",
    "DecisionResolution",
    "PartyDecision",
    "PartyDecisionResolver",
    "PartyVote",
    "PartyParticipation",
    "PartyParticipationResolver",
    "ParticipationResolution",
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
