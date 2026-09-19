"""Motor de combate determinístico para D&D 5e (2014).

Esta camada resolve somente mecânica. Narração, Telegram e IA ficam fora dela.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .character import Character
from .dice import DiceRoll, roll, roll_d20
from .rules import ability_modifier


@dataclass
class Combatant:
    """Participante de combate com estado mínimo independente de personagem."""

    name: str
    armor_class: int
    max_hp: int
    hp: int
    dexterity: int = 10
    attack_bonus: int = 0
    damage_dice: str = "1d4"
    damage_bonus: int = 0
    is_player: bool = False
    initiative: int | None = None

    def __post_init__(self) -> None:
        if self.armor_class < 1:
            raise ValueError("Classe de armadura deve ser positiva.")
        if self.max_hp < 1:
            raise ValueError("HP máximo deve ser positivo.")
        if not 0 <= self.hp <= self.max_hp:
            raise ValueError("HP atual deve estar entre 0 e o HP máximo.")

    @property
    def dexterity_modifier(self) -> int:
        return ability_modifier(self.dexterity)

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("Dano não pode ser negativo.")
        dealt = min(amount, self.hp)
        self.hp -= dealt
        return dealt


@dataclass(frozen=True)
class InitiativeResult:
    combatant: str
    roll: DiceRoll
    modifier: int
    total: int


@dataclass(frozen=True)
class AttackResult:
    attacker: str
    target: str
    roll: DiceRoll
    attack_bonus: int
    total: int
    armor_class: int
    hit: bool
    critical: bool
    fumble: bool
    damage_roll: DiceRoll | None
    damage: int


@dataclass
class CombatState:
    combatants: list[Combatant]
    turn_index: int = 0
    round: int = 1
    started: bool = False

    def __post_init__(self) -> None:
        if not self.combatants:
            raise ValueError("Um combate precisa de pelo menos dois combatentes.")
        if len(self.combatants) < 2:
            raise ValueError("Um combate precisa de pelo menos dois combatentes.")

    @property
    def current(self) -> Combatant:
        alive = [c for c in self.combatants if c.is_alive]
        if not alive:
            raise RuntimeError("O combate terminou.")
        if not self.started:
            raise RuntimeError("O combate ainda não foi iniciado.")
        current = self.combatants[self.turn_index]
        if not current.is_alive:
            self.advance_turn()
            return self.current
        return current

    @property
    def finished(self) -> bool:
        return len({c.is_player for c in self.combatants if c.is_alive}) <= 1

    def start(self, rng=None) -> list[InitiativeResult]:
        """Rola iniciativa e ordena o combate por maior resultado."""
        results = []
        for combatant in self.combatants:
            roll_result = roll_d20(rng=rng)
            total = roll_result.total + combatant.dexterity_modifier
            combatant.initiative = total
            results.append(
                InitiativeResult(
                    combatant=combatant.name,
                    roll=roll_result,
                    modifier=combatant.dexterity_modifier,
                    total=total,
                )
            )

        # Empate: maior modificador de Destreza primeiro; persistindo empate,
        # ordem original. Isso mantém a resolução determinística sem depender
        # de aleatoriedade adicional.
        original_order = {id(c): i for i, c in enumerate(self.combatants)}
        self.combatants.sort(
            key=lambda c: (
                c.initiative if c.initiative is not None else -10**9,
                c.dexterity_modifier,
                -original_order[id(c)],
            ),
            reverse=True,
        )
        self.turn_index = 0
        self.round = 1
        self.started = True
        return results

    def advance_turn(self) -> Combatant:
        if not self.started:
            raise RuntimeError("O combate ainda não foi iniciado.")
        if self.finished:
            raise RuntimeError("O combate terminou.")

        attempts = 0
        while attempts < len(self.combatants):
            self.turn_index = (self.turn_index + 1) % len(self.combatants)
            if self.turn_index == 0:
                self.round += 1
            if self.combatants[self.turn_index].is_alive:
                return self.combatants[self.turn_index]
            attempts += 1

        raise RuntimeError("Nenhum combatente vivo pode jogar.")

    def attack(
        self,
        attacker: Combatant,
        target: Combatant,
        *,
        advantage: bool = False,
        disadvantage: bool = False,
        rng=None,
    ) -> AttackResult:
        """Resolve um ataque, incluindo crítico, 1 natural e dano."""
        if not attacker.is_alive:
            raise ValueError("Um combatente incapacitado não pode atacar.")
        if not target.is_alive:
            raise ValueError("O alvo já está fora de combate.")

        attack_roll = roll_d20(
            advantage=advantage,
            disadvantage=disadvantage,
            rng=rng,
        )
        natural = attack_roll.natural
        critical = natural == 20
        fumble = natural == 1
        total = attack_roll.total + attacker.attack_bonus
        hit = critical or (not fumble and total >= target.armor_class)

        damage_roll = None
        damage = 0
        if hit:
            damage_roll = roll_expression_for_damage(
                attacker.damage_dice,
                rng=rng,
                critical=critical,
            )
            damage = max(0, damage_roll.total + attacker.damage_bonus)
            target.take_damage(damage)

        return AttackResult(
            attacker=attacker.name,
            target=target.name,
            roll=attack_roll,
            attack_bonus=attacker.attack_bonus,
            total=total,
            armor_class=target.armor_class,
            hit=hit,
            critical=critical,
            fumble=fumble,
            damage_roll=damage_roll,
            damage=damage,
        )


def roll_expression_for_damage(
    expression: str,
    *,
    rng=None,
    critical: bool = False,
) -> DiceRoll:
    """Rola dano simples; crítico dobra a quantidade de dados."""
    normalized = expression.strip().lower().replace(" ", "")
    if "d" not in normalized:
        raise ValueError(f"Dado de dano inválido: {expression!r}")

    quantity_text, sides_text = normalized.split("d", 1)
    quantity = int(quantity_text or 1)
    sides = int(sides_text)
    if quantity < 1 or sides < 2:
        raise ValueError(f"Dado de dano inválido: {expression!r}")

    return roll(sides, quantity * (2 if critical else 1), rng)


def combatant_from_character(
    character: Character,
    *,
    attack_bonus: int = 0,
    damage_dice: str = "1d4",
    damage_bonus: int = 0,
) -> Combatant:
    """Cria um combatente usando o estado mecânico de um personagem."""
    return Combatant(
        name=character.name,
        armor_class=character.armor_class,
        max_hp=character.max_hp,
        hp=character.hp,
        dexterity=character.abilities["Destreza"],
        attack_bonus=attack_bonus,
        damage_dice=damage_dice,
        damage_bonus=damage_bonus,
        is_player=True,
    )
