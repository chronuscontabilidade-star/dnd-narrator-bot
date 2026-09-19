"""Economia de ações e turnos de combate para D&D 5e 2014.

O motor mantém o estado mecânico. A camada de IA pode escolher/interpretar
uma ação, mas não pode ignorar as regras de turno, movimento ou alvo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .character import Character
from .dice import DiceRoll, roll, roll_d20
from .rules import ability_modifier


class ActionType(str, Enum):
    ATTACK = "attack"
    DASH = "dash"
    DODGE = "dodge"
    DISENGAGE = "disengage"
    HELP = "help"
    READY = "ready"
    SEARCH = "search"
    END_TURN = "end_turn"


@dataclass
class Combatant:
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
    speed: int = 30
    position: tuple[int, int] = (0, 0)

    def __post_init__(self) -> None:
        if self.armor_class < 1:
            raise ValueError("Classe de armadura deve ser positiva.")
        if self.max_hp < 1:
            raise ValueError("HP máximo deve ser positivo.")
        if not 0 <= self.hp <= self.max_hp:
            raise ValueError("HP atual deve estar entre 0 e o HP máximo.")
        if self.speed < 0:
            raise ValueError("Deslocamento não pode ser negativo.")

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


@dataclass
class TurnState:
    """Recursos disponíveis durante o turno atual."""

    movement_remaining: int
    action_used: bool = False
    bonus_action_used: bool = False
    reaction_available: bool = True
    dash_used: bool = False
    dodge_active: bool = False
    disengaged: bool = False

    def reset(self, speed: int) -> None:
        self.movement_remaining = speed
        self.action_used = False
        self.bonus_action_used = False
        self.reaction_available = True
        self.dash_used = False
        self.dodge_active = False
        self.disengaged = False


@dataclass(frozen=True)
class InitiativeResult:
    combatant: str
    roll: DiceRoll
    modifier: int
    total: int


@dataclass(frozen=True)
class MoveResult:
    combatant: str
    from_position: tuple[int, int]
    to_position: tuple[int, int]
    distance: int
    remaining_movement: int


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
    turn_states: dict[str, TurnState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.combatants) < 2:
            raise ValueError("Um combate precisa de pelo menos dois combatentes.")

    @property
    def current(self) -> Combatant:
        if not self.started:
            raise RuntimeError("O combate ainda não foi iniciado.")
        if self.finished:
            raise RuntimeError("O combate terminou.")
        current = self.combatants[self.turn_index]
        if not current.is_alive:
            return self.advance_turn()
        return current

    @property
    def current_turn(self) -> TurnState:
        current = self.current
        return self.turn_states[current.name]

    @property
    def finished(self) -> bool:
        alive_sides = {c.is_player for c in self.combatants if c.is_alive}
        return len(alive_sides) <= 1

    def _require_current(self, combatant: Combatant) -> None:
        if not self.started:
            raise RuntimeError("O combate ainda não foi iniciado.")
        if self.finished:
            raise ValueError("O combate terminou.")
        if combatant is not self.current:
            raise ValueError("Não é o turno desse combatente.")
        if not combatant.is_alive:
            raise ValueError("Esse combatente está fora de combate.")

    def _state_for(self, combatant: Combatant) -> TurnState:
        try:
            return self.turn_states[combatant.name]
        except KeyError as exc:
            raise RuntimeError("Estado de turno não encontrado.") from exc

    def start(self, rng=None) -> list[InitiativeResult]:
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
        self.turn_states = {
            c.name: TurnState(c.speed) for c in self.combatants
        }
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
            candidate = self.combatants[self.turn_index]
            if candidate.is_alive:
                self.turn_states[candidate.name].reset(candidate.speed)
                return candidate
            attempts += 1

        raise RuntimeError("Nenhum combatente vivo pode jogar.")

    @staticmethod
    def _grid_distance(origin: tuple[int, int], target: tuple[int, int]) -> int:
        """Distância em pés usando o deslocamento de grade de 5 pés."""
        dx = abs(target[0] - origin[0])
        dy = abs(target[1] - origin[1])
        return max(dx, dy) * 5

    def move_to(self, combatant: Combatant, position: tuple[int, int]) -> MoveResult:
        """Move o combatente dentro do deslocamento restante do turno."""
        self._require_current(combatant)
        state = self._state_for(combatant)
        distance = self._grid_distance(combatant.position, position)
        if distance > state.movement_remaining:
            raise ValueError("Movimento excede o deslocamento restante.")

        old_position = combatant.position
        combatant.position = position
        state.movement_remaining -= distance
        return MoveResult(
            combatant=combatant.name,
            from_position=old_position,
            to_position=position,
            distance=distance,
            remaining_movement=state.movement_remaining,
        )

    def dash(self, combatant: Combatant) -> int:
        """Ação Dash: acrescenta deslocamento igual ao Speed."""
        self._require_current(combatant)
        state = self._state_for(combatant)
        if state.action_used:
            raise ValueError("Ação já utilizada neste turno.")
        state.action_used = True
        state.dash_used = True
        state.movement_remaining += combatant.speed
        return state.movement_remaining

    def dodge(self, combatant: Combatant) -> None:
        self._require_current(combatant)
        state = self._state_for(combatant)
        if state.action_used:
            raise ValueError("Ação já utilizada neste turno.")
        state.action_used = True
        state.dodge_active = True

    def disengage(self, combatant: Combatant) -> None:
        self._require_current(combatant)
        state = self._state_for(combatant)
        if state.action_used:
            raise ValueError("Ação já utilizada neste turno.")
        state.action_used = True
        state.disengaged = True

    def end_turn(self, combatant: Combatant) -> Combatant:
        self._require_current(combatant)
        return self.advance_turn()

    def attack(
        self,
        attacker: Combatant,
        target: Combatant,
        *,
        advantage: bool = False,
        disadvantage: bool = False,
        rng=None,
    ) -> AttackResult:
        """Usa a ação Attack contra um alvo dentro do alcance corpo a corpo."""
        self._require_current(attacker)
        state = self._state_for(attacker)
        if state.action_used:
            raise ValueError("Ação já utilizada neste turno.")
        if not target.is_alive:
            raise ValueError("O alvo já está fora de combate.")
        if target is attacker:
            raise ValueError("Um combatente não pode atacar a si mesmo.")

        distance = self._grid_distance(attacker.position, target.position)
        if distance > 5:
            raise ValueError("O alvo está fora do alcance corpo a corpo.")

        attack_roll = roll_d20(
            advantage=advantage,
            disadvantage=disadvantage or self._state_for(target).dodge_active,
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

        state.action_used = True
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
