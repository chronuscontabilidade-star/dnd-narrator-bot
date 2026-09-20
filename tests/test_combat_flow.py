import unittest

from dnd_bot.game.action import ActionResolver
from dnd_bot.game.combat_flow import (
    combatant_from_enemy,
    combatant_from_player_record,
    find_pending_combat_encounter,
    start_pending_combat,
)


class CombatFlowTests(unittest.TestCase):
    def adventure(self):
        return {
            "progresso": {"local_atual": "cripta"},
            "locais": [{"id": "cripta", "nome": "Cripta", "conexoes": []}],
            "encounters": [{
                "id": "enc-1",
                "local": "cripta",
                "tipo": "combate",
                "status": "pendente",
                "inimigos": [{"nome": "Goblin", "hp": 7, "ca": 10}],
            }],
            "combate": None,
        }

    def player(self):
        return {
            "nome": "Kira",
            "atributos": {
                "Força": 14,
                "Destreza": 14,
                "Constituição": 12,
                "Inteligência": 10,
                "Sabedoria": 10,
                "Carisma": 10,
            },
        }

    def test_finds_pending_encounter_at_current_location(self):
        found = find_pending_combat_encounter(self.adventure())
        self.assertEqual(found[0], "enc-1")

    def test_starts_combat_from_structured_encounter(self):
        adventure = self.adventure()
        combat, encounter_id = start_pending_combat(adventure, [self.player()])
        self.assertIsNotNone(combat)
        self.assertEqual(encounter_id, "enc-1")
        self.assertTrue(combat.started)
        self.assertIn("combate", adventure)
        self.assertEqual(adventure["combate"]["encounter_id"], "enc-1")
        self.assertTrue(any(c.is_player for c in combat.combatants))
        self.assertTrue(any(not c.is_player for c in combat.combatants))

    def test_attack_intent_can_be_resolved_after_starting_encounter(self):
        adventure = self.adventure()
        combat, _ = start_pending_combat(adventure, [self.player()])
        intent = ActionResolver(adventure).resolve("atacar Goblin")
        self.assertEqual(intent.tipo, "ataque")
        self.assertEqual(intent.alvo, "Goblin")

    def test_enemy_defaults_are_mechanical_and_valid(self):
        enemy = combatant_from_enemy("Goblin", 1)
        self.assertEqual(enemy.name, "Goblin")
        self.assertEqual(enemy.hp, 7)
        self.assertFalse(enemy.is_player)

    def test_player_defaults_produce_valid_combatant(self):
        player = combatant_from_player_record(self.player())
        self.assertEqual(player.name, "Kira")
        self.assertEqual(player.max_hp, 11)
        self.assertTrue(player.is_player)


if __name__ == "__main__":
    unittest.main()
