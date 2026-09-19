"""Regras de geração de atributos para D&D 5e (2014).

A criação automatizada usa o método de rolagem previsto nas regras:
4d6, descarta o menor dado, seis vezes. A raça aplica apenas os bônus
raciais correspondentes. Classe não concede bônus de atributo.
"""

from __future__ import annotations

import random


ATTRIBUTES = ("Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma")

# Bônus raciais das opções atualmente oferecidas pelo bot em D&D 5e 2014.
RACIAL_BONUSES = {
    "Humano": {"Força": 1, "Destreza": 1, "Constituição": 1, "Inteligência": 1, "Sabedoria": 1, "Carisma": 1},
    "Elfo": {"Destreza": 2, "Inteligência": 1},
    "Anão": {"Constituição": 2, "Sabedoria": 1},
    "Halfling": {"Destreza": 2, "Carisma": 1},
    "Tiefling": {"Inteligência": 1, "Carisma": 2},
    "Meio-Orc": {"Força": 2, "Constituição": 1},
}

# Prioridades para distribuir os seis resultados quando o jogador não
# escolheu manualmente. Isso é apenas uma decisão de criação, não bônus de classe.
CLASS_PRIORITIES = {
    "Guerreiro": ("Força", "Constituição", "Destreza", "Sabedoria", "Carisma", "Inteligência"),
    "Bárbaro": ("Força", "Constituição", "Destreza", "Sabedoria", "Carisma", "Inteligência"),
    "Ladino": ("Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma", "Força"),
    "Mago": ("Inteligência", "Destreza", "Constituição", "Sabedoria", "Carisma", "Força"),
    "Clérigo": ("Sabedoria", "Constituição", "Força", "Destreza", "Carisma", "Inteligência"),
    "Ranger": ("Destreza", "Sabedoria", "Constituição", "Força", "Inteligência", "Carisma"),
}


def rolar_atributo(rng=None) -> tuple[int, list[int]]:
    """Rola 4d6 e descarta o menor resultado."""
    rng = rng or random
    dados = [rng.randint(1, 6) for _ in range(4)]
    return sum(sorted(dados, reverse=True)[:3]), dados


def gerar_atributos(classe: str, raca: str, rng=None) -> dict:
    """Gera seis atributos usando 4d6-drop-lowest e aplica bônus raciais."""
    rng = rng or random
    resultados = [rolar_atributo(rng)[0] for _ in ATTRIBUTES]
    resultados.sort(reverse=True)

    prioridades = CLASS_PRIORITIES.get(classe, ATTRIBUTES)
    atributos = dict(zip(prioridades, resultados))

    for atributo, bonus in RACIAL_BONUSES.get(raca, {}).items():
        atributos[atributo] = atributos.get(atributo, 10) + bonus

    return atributos


def aplicar_bonuses_raciais(atributos: dict, raca: str) -> dict:
    """Aplica apenas os bônus raciais, sem alterar a distribuição escolhida."""
    result = {nome: int(atributos.get(nome, 10)) for nome in ATTRIBUTES}
    for atributo, bonus in RACIAL_BONUSES.get(raca, {}).items():
        result[atributo] += bonus
    return result


__all__ = [
    "ATTRIBUTES",
    "RACIAL_BONUSES",
    "CLASS_PRIORITIES",
    "rolar_atributo",
    "gerar_atributos",
    "aplicar_bonuses_raciais",
]
