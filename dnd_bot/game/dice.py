"""Rolagens determinísticas e testáveis para o motor de jogo."""

from __future__ import annotations

from dataclasses import dataclass
import random
import re
from typing import Protocol


class RandomSource(Protocol):
    def randint(self, a: int, b: int) -> int: ...


@dataclass(frozen=True)
class DiceRoll:
    """Resultado imutável de uma rolagem."""

    sides: int
    rolls: tuple[int, ...]
    total: int
    selected: int | None = None

    @property
    def natural(self) -> int | None:
        return self.selected if self.selected is not None else (
            self.rolls[0] if len(self.rolls) == 1 else None
        )


def _rng(rng: RandomSource | None) -> RandomSource:
    return rng or random.SystemRandom()


def roll(sides: int, quantity: int = 1, rng: RandomSource | None = None) -> DiceRoll:
    """Rola NdX sem conhecer nenhuma regra de personagem."""
    if sides < 2:
        raise ValueError("Um dado precisa ter pelo menos 2 lados.")
    if quantity < 1:
        raise ValueError("A quantidade de dados deve ser positiva.")

    source = _rng(rng)
    rolls = tuple(source.randint(1, sides) for _ in range(quantity))
    return DiceRoll(sides=sides, rolls=rolls, total=sum(rolls))


def roll_d20(
    *,
    advantage: bool = False,
    disadvantage: bool = False,
    rng: RandomSource | None = None,
) -> DiceRoll:
    """Rola d20 normal, com vantagem ou com desvantagem.

    Vantagem e desvantagem simultâneas se anulam.
    """
    if advantage and disadvantage:
        advantage = disadvantage = False

    if not advantage and not disadvantage:
        return roll(20, 1, rng)

    source = _rng(rng)
    rolls = (source.randint(1, 20), source.randint(1, 20))
    selected = max(rolls) if advantage else min(rolls)
    return DiceRoll(sides=20, rolls=rolls, total=selected, selected=selected)


_DICE_RE = re.compile(r"^(?P<quantity>[1-9]\d*)d(?P<sides>[2-9]\d*)(?P<modifier>[+-]\d+)?$")


def roll_expression(expression: str, rng: RandomSource | None = None) -> DiceRoll:
    """Rola expressões simples como 2d6, d20 ou 2d8+3.

    Esta função não conhece armas, magias ou classes. Ela só resolve dados.
    """
    normalized = expression.strip().lower().replace(" ", "")
    if normalized.startswith("d"):
        normalized = "1" + normalized

    match = _DICE_RE.fullmatch(normalized)
    if not match:
        raise ValueError(f"Expressão de dado inválida: {expression!r}")

    quantity = int(match.group("quantity"))
    sides = int(match.group("sides"))
    modifier = int(match.group("modifier") or 0)
    result = roll(sides, quantity, rng)
    return DiceRoll(
        sides=sides,
        rolls=result.rolls,
        total=result.total + modifier,
    )
