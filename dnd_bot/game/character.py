"""Modelo mecânico mínimo de personagem."""

from __future__ import annotations

from dataclasses import dataclass, field

from .rules import ABILITIES, ability_modifier, proficiency_bonus


@dataclass
class Character:
    """Estado mecânico essencial para o primeiro vertical slice."""

    name: str
    race: str
    class_name: str
    abilities: dict[str, int] = field(default_factory=lambda: {
        ability: 10 for ability in ABILITIES
    })
    level: int = 1
    max_hp: int = 1
    hp: int = 1
    armor_class: int = 10
    proficient_abilities: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        missing = set(ABILITIES) - set(self.abilities)
        if missing:
            raise ValueError(f"Atributos ausentes: {sorted(missing)}")
        invalid = {name for name, value in self.abilities.items() if not isinstance(value, int)}
        if invalid:
            raise TypeError(f"Atributos precisam ser inteiros: {sorted(invalid)}")
        if self.level < 1 or self.level > 20:
            raise ValueError("O nível deve estar entre 1 e 20.")
        if self.max_hp < 1:
            raise ValueError("HP máximo deve ser positivo.")
        if not 0 <= self.hp <= self.max_hp:
            raise ValueError("HP atual deve estar entre 0 e o HP máximo.")
        if self.armor_class < 1:
            raise ValueError("Classe de armadura deve ser positiva.")

    @property
    def proficiency_bonus(self) -> int:
        return proficiency_bonus(self.level)

    def modifier(self, ability: str) -> int:
        if ability not in self.abilities:
            raise KeyError(f"Atributo desconhecido: {ability}")
        return ability_modifier(self.abilities[ability])

    def is_alive(self) -> bool:
        return self.hp > 0
