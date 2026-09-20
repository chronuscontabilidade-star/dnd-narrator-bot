"""Integração entre encontros estruturados e o motor de combate."""

from __future__ import annotations

from .combat import CombatState, Combatant
from .rules import ability_modifier


def combatant_from_player_record(player: dict) -> Combatant:
    attrs = player.get("atributos") or {}
    dex = int(attrs.get("Destreza", 10))
    con = int(attrs.get("Constituição", 10))
    strength = int(attrs.get("Força", 10))
    con_mod = ability_modifier(con)
    return Combatant(
        name=player["nome"],
        armor_class=max(1, int(player.get("ca", 10 + ability_modifier(dex)))),
        max_hp=max(1, int(player.get("hp_max", 10 + con_mod))),
        hp=max(0, min(int(player.get("hp", player.get("hp_max", 10 + con_mod))), int(player.get("hp_max", 10 + con_mod)))),
        dexterity=dex,
        attack_bonus=2 + ability_modifier(strength),
        damage_dice="1d6",
        damage_bonus=ability_modifier(strength),
        is_player=True,
        position=(0, 0),
    )


def combatant_from_enemy(raw, index: int) -> Combatant:
    if isinstance(raw, str):
        raw = {"nome": raw}
    if not isinstance(raw, dict):
        raw = {}
    name = str(raw.get("nome") or raw.get("name") or f"Inimigo {index}").strip()
    dex = int(raw.get("destreza", raw.get("dexterity", 10)))
    hp = int(raw.get("hp", raw.get("max_hp", 7)))
    max_hp = max(1, int(raw.get("max_hp", hp)))
    pos = raw.get("position", [1, 0])
    if not isinstance(pos, (list, tuple)) or len(pos) != 2:
        pos = [1, 0]
    return Combatant(
        name=name,
        armor_class=max(1, int(raw.get("ca", raw.get("armor_class", 10)))),
        max_hp=max_hp,
        hp=max(0, min(hp, max_hp)),
        dexterity=dex,
        attack_bonus=int(raw.get("attack_bonus", 2)),
        damage_dice=str(raw.get("damage_dice", "1d6")),
        damage_bonus=int(raw.get("damage_bonus", 0)),
        is_player=False,
        position=(int(pos[0]), int(pos[1])),
    )


def find_pending_combat_encounter(adventure: dict) -> tuple[str, dict] | None:
    progress = (adventure or {}).get("progresso") or {}
    current_location = progress.get("local_atual")
    for encounter in (adventure or {}).get("encounters", []):
        if (
            isinstance(encounter, dict)
            and encounter.get("local") == current_location
            and encounter.get("tipo") == "combate"
            and encounter.get("status", "pendente") == "pendente"
            and encounter.get("inimigos")
        ):
            return str(encounter.get("id")), encounter
    return None


def start_pending_combat(
    adventure: dict,
    players: list[dict],
) -> tuple[CombatState | None, str | None]:
    raw = (adventure or {}).get("combate")
    if raw:
        return CombatState.from_dict(raw), raw.get("encounter_id")

    found = find_pending_combat_encounter(adventure)
    if not found:
        return None, None

    encounter_id, encounter = found
    combatants = [combatant_from_player_record(player) for player in players]
    combatants.extend(
        combatant_from_enemy(enemy, index)
        for index, enemy in enumerate(encounter.get("inimigos", []), 1)
    )
    if len(combatants) < 2:
        return None, None

    combat = CombatState(combatants)
    combat.start()
    raw_combat = combat.to_dict()
    raw_combat["encounter_id"] = encounter_id
    adventure["combate"] = raw_combat
    return combat, encounter_id


def run_enemy_turns(combat: CombatState) -> list[dict]:
    results = []
    while combat.started and not combat.finished and not combat.current.is_player:
        enemy = combat.current
        target = next(
            (item for item in combat.combatants if item.is_player and item.is_alive),
            None,
        )
        if target is None:
            break
        try:
            result = combat.attack(enemy, target)
            results.append({
                "inimigo": enemy.name,
                "alvo": target.name,
                "acertou": result.hit,
                "critico": result.critical,
                "dano": result.damage,
                "hp_alvo": target.hp,
            })
            if not combat.finished:
                combat.end_turn(enemy)
        except (RuntimeError, ValueError):
            try:
                combat.end_turn(enemy)
            except (RuntimeError, ValueError):
                break
    return results
