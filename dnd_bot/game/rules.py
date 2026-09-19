"""Regras fundamentais de d20 usadas pelo motor.

Este módulo não conhece Telegram nem IA. Ele recebe números e devolve
resultados mecânicos previsíveis.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dice import DiceRoll, roll_d20


ABILITIES = (
    "Força",
    "Destreza",
    "Constituição",
    "Inteligência",
    "Sabedoria",
    "Carisma",
)


def ability_modifier(score: int) -> int:
    """Calcula o modificador de atributo padrão de D&D."""
    if not isinstance(score, int):
        raise TypeError("O valor do atributo deve ser inteiro.")
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """Bônus de proficiência por nível, limitado ao intervalo jogável 1-20."""
    if not isinstance(level, int):
        raise TypeError("O nível deve ser inteiro.")
    if not 1 <= level <= 20:
        raise ValueError("O nível deve estar entre 1 e 20.")
    return 2 + ((level - 1) // 4)


@dataclass(frozen=True)
class CheckResult:
    roll: DiceRoll
    modifier: int
    total: int
    dc: int
    success: bool

    @property
    def natural(self) -> int | None:
        return self.roll.natural


def ability_check(
    score: int,
    dc: int,
    *,
    proficiency: bool = False,
    level: int = 1,
    advantage: bool = False,
    disadvantage: bool = False,
    rng=None,
) -> CheckResult:
    """Resolve um teste de atributo contra uma CD."""
    if not 1 <= dc <= 30:
        raise ValueError("A CD deve estar entre 1 e 30.")

    modifier = ability_modifier(score)
    if proficiency:
        modifier += proficiency_bonus(level)

    result = roll_d20(
        advantage=advantage,
        disadvantage=disadvantage,
        rng=rng,
    )
    total = result.total + modifier
    return CheckResult(
        roll=result,
        modifier=modifier,
        total=total,
        dc=dc,
        success=total >= dc,
    )


def saving_throw(
    score: int,
    dc: int,
    *,
    proficiency: bool = False,
    level: int = 1,
    advantage: bool = False,
    disadvantage: bool = False,
    rng=None,
) -> CheckResult:
    """Saving throw. A mecânica base é a mesma de um teste d20."""
    return ability_check(
        score,
        dc,
        proficiency=proficiency,
        level=level,
        advantage=advantage,
        disadvantage=disadvantage,
        rng=rng,
    )
