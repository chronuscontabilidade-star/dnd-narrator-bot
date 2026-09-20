import unittest

from dnd_bot.game.combat import CombatState, Combatant, combatant_from_character
from dnd_bot.game.character import Character


class FixedRng:
    def __init__(self, values):
        self.values = iter(values)

    def randint(self, _a, _b):
        return next(self.values)


def started_combat(hero, goblin, initiative=(10, 10)):
    combat = CombatState([hero, goblin])
    combat.start(FixedRng(initiative))
    return combat


class CombatTests(unittest.TestCase):
    def test_initiative_orders_highest_first(self):
        hero = Combatant("Heroi", 12, 10, 10, dexterity=16, is_player=True)
        goblin = Combatant("Goblin", 12, 7, 7, dexterity=12)
        combat = CombatState([hero, goblin])
        combat.start(FixedRng([8, 18]))

        self.assertEqual([c.name for c in combat.combatants], ["Goblin", "Heroi"])
        self.assertEqual(combat.current.name, "Goblin")

    def test_turn_advances_and_rounds(self):
        hero = Combatant("Heroi", 12, 10, 10, dexterity=16, is_player=True)
        goblin = Combatant("Goblin", 12, 7, 7, dexterity=12)
        combat = CombatState([hero, goblin])
        combat.start(FixedRng([10, 10]))

        self.assertEqual(combat.current.name, "Heroi")
        combat.advance_turn()
        self.assertEqual(combat.current.name, "Goblin")
        combat.advance_turn()
        self.assertEqual(combat.current.name, "Heroi")
        self.assertEqual(combat.round, 2)

    def test_movement_consumes_turn_movement(self):
        hero = Combatant("Heroi", 12, 10, 10, speed=30, is_player=True)
        goblin = Combatant("Goblin", 12, 7, 7, position=(10, 0))
        combat = started_combat(hero, goblin)

        result = combat.move_to(hero, (4, 0))
        self.assertEqual(result.distance, 20)
        self.assertEqual(result.remaining_movement, 10)
        self.assertEqual(hero.position, (4, 0))

    def test_movement_cannot_exceed_speed(self):
        hero = Combatant("Heroi", 12, 10, 10, speed=30, is_player=True)
        goblin = Combatant("Goblin", 12, 7, 7)
        combat = started_combat(hero, goblin)

        with self.assertRaises(ValueError):
            combat.move_to(hero, (7, 0))

    def test_dash_adds_speed_to_movement(self):
        hero = Combatant("Heroi", 12, 10, 10, speed=30, is_player=True)
        goblin = Combatant("Goblin", 12, 7, 7)
        combat = started_combat(hero, goblin)

        self.assertEqual(combat.dash(hero), 60)
        combat.move_to(hero, (12, 0))
        self.assertEqual(combat.current_turn.movement_remaining, 0)

    def test_attack_requires_current_turn(self):
        hero = Combatant("Heroi", 12, 10, 10, is_player=True)
        goblin = Combatant("Goblin", 12, 7, 7)
        combat = started_combat(hero, goblin)

        with self.assertRaises(ValueError):
            combat.attack(goblin, hero, rng=FixedRng([10]))

    def test_attack_consumes_action_and_applies_damage(self):
        hero = Combatant(
            "Heroi", 12, 10, 10, dexterity=14, attack_bonus=5,
            damage_dice="1d8", damage_bonus=3, is_player=True
        )
        goblin = Combatant("Goblin", 12, 7, 7, position=(1, 0))
        combat = started_combat(hero, goblin)

        result = combat.attack(hero, goblin, rng=FixedRng([10, 5]))

        self.assertTrue(result.hit)
        self.assertEqual(result.total, 15)
        self.assertEqual(result.damage, 8)
        self.assertEqual(goblin.hp, 0)
        with self.assertRaises(ValueError):
            combat.attack(hero, goblin, rng=FixedRng([10]))

    def test_attack_requires_target_in_melee_range(self):
        hero = Combatant("Heroi", 12, 10, 10, is_player=True)
        goblin = Combatant("Goblin", 12, 7, 7, position=(2, 0))
        combat = started_combat(hero, goblin)

        with self.assertRaises(ValueError):
            combat.attack(hero, goblin, rng=FixedRng([10]))

    def test_natural_one_misses_even_with_bonus(self):
        hero = Combatant("Heroi", 20, 10, 10, attack_bonus=99, is_player=True)
        goblin = Combatant("Goblin", 10, 7, 7, position=(1, 0))
        combat = started_combat(hero, goblin)
        result = combat.attack(hero, goblin, rng=FixedRng([1]))

        self.assertFalse(result.hit)
        self.assertTrue(result.fumble)
        self.assertEqual(result.damage, 0)

    def test_natural_twenty_is_critical_and_doubles_dice(self):
        hero = Combatant(
            "Heroi", 10, 10, 10, attack_bonus=0,
            damage_dice="1d6", damage_bonus=2, is_player=True
        )
        goblin = Combatant("Goblin", 10, 20, 20, position=(1, 0))
        combat = started_combat(hero, goblin)
        result = combat.attack(hero, goblin, rng=FixedRng([20, 3, 4]))

        self.assertTrue(result.critical)
        self.assertEqual(result.damage, 9)
        self.assertEqual(goblin.hp, 11)

    def test_dodge_gives_disadvantage_to_attack(self):
        hero = Combatant("Heroi", 10, 10, 10, is_player=True)
        goblin = Combatant("Goblin", 10, 20, 20, position=(1, 0))
        combat = started_combat(hero, goblin)

        combat.dodge(hero)
        combat.advance_turn()
        result = combat.attack(goblin, hero, rng=FixedRng([18, 4]))
        self.assertEqual(result.roll.rolls, (18, 4))
        self.assertEqual(result.roll.total, 4)

    def test_end_turn_changes_player(self):
        hero = Combatant("Heroi", 10, 10, 10, is_player=True)
        goblin = Combatant("Goblin", 10, 7, 7)
        combat = started_combat(hero, goblin)

        self.assertEqual(combat.current.name, "Heroi")
        combat.end_turn(hero)
        self.assertEqual(combat.current.name, "Goblin")

    def test_combat_ends_when_one_side_is_defeated(self):
        hero = Combatant("Heroi", 10, 10, 10, is_player=True)
        goblin = Combatant("Goblin", 10, 5, 0)
        combat = CombatState([hero, goblin])
        self.assertTrue(combat.finished)

    def test_finished_combat_rejects_new_actions(self):
        hero = Combatant("Heroi", 10, 10, 0, is_player=True)
        goblin = Combatant("Goblin", 10, 0, 0, position=(1, 0))
        combat = CombatState([hero, goblin])
        combat.start(FixedRng([10, 10]))
        self.assertTrue(combat.finished)
        with self.assertRaises((RuntimeError, ValueError)):
            combat.attack(hero, goblin, rng=FixedRng([10]))

    def test_duplicate_combatant_names_are_rejected(self):
        hero = Combatant("Heroi", 12, 10, 10, is_player=True)
        duplicate = Combatant("Heroi", 12, 10, 10)
        with self.assertRaises(ValueError):
            CombatState([hero, duplicate])

    def test_combat_requires_both_sides_alive_before_start(self):
        hero = Combatant("Heroi", 12, 10, 10, is_player=True)
        fallen_enemy = Combatant("Goblin", 12, 7, 0)
        combat = CombatState([hero, fallen_enemy])
        with self.assertRaises(ValueError):
            combat.start(FixedRng([10, 10]))

    def test_combat_cannot_start_twice(self):
        hero = Combatant("Heroi", 12, 10, 10, is_player=True)
        goblin = Combatant("Goblin", 12, 7, 7)
        combat = started_combat(hero, goblin)
        with self.assertRaises(RuntimeError):
            combat.start(FixedRng([10, 10]))

    def test_character_conversion(self):
        character = Character(
            name="Kira",
            race="Elfa",
            class_name="Ladina",
            abilities={
                "Força": 10, "Destreza": 16, "Constituição": 12,
                "Inteligência": 10, "Sabedoria": 11, "Carisma": 13,
            },
            max_hp=10,
            hp=10,
            armor_class=14,
        )
        combatant = combatant_from_character(
            character, attack_bonus=5, damage_dice="1d6"
        )
        self.assertEqual(combatant.name, "Kira")
        self.assertEqual(combatant.armor_class, 14)
        self.assertEqual(combatant.hp, 10)


if __name__ == "__main__":
    unittest.main()
