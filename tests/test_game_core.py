import unittest

from dnd_bot.game.character import Character
from dnd_bot.game.dice import roll, roll_d20, roll_expression
from dnd_bot.game.engine import GameEngine
from dnd_bot.game.rules import ability_check, ability_modifier, proficiency_bonus


class FixedRng:
    def __init__(self, values):
        self.values = iter(values)

    def randint(self, _a, _b):
        return next(self.values)


class DiceTests(unittest.TestCase):
    def test_roll_is_deterministic_with_injected_rng(self):
        result = roll(6, 2, FixedRng([2, 5]))
        self.assertEqual(result.rolls, (2, 5))
        self.assertEqual(result.total, 7)

    def test_d20_advantage_uses_highest(self):
        result = roll_d20(advantage=True, rng=FixedRng([3, 17]))
        self.assertEqual(result.rolls, (3, 17))
        self.assertEqual(result.total, 17)

    def test_d20_disadvantage_uses_lowest(self):
        result = roll_d20(disadvantage=True, rng=FixedRng([18, 4]))
        self.assertEqual(result.total, 4)

    def test_advantage_and_disadvantage_cancel(self):
        result = roll_d20(advantage=True, disadvantage=True, rng=FixedRng([11]))
        self.assertEqual(result.rolls, (11,))

    def test_expression_supports_modifier(self):
        result = roll_expression("2d6+3", FixedRng([2, 4]))
        self.assertEqual(result.rolls, (2, 4))
        self.assertEqual(result.total, 9)


class RulesTests(unittest.TestCase):
    def test_ability_modifier(self):
        self.assertEqual(ability_modifier(8), -1)
        self.assertEqual(ability_modifier(10), 0)
        self.assertEqual(ability_modifier(17), 3)

    def test_proficiency_bonus(self):
        self.assertEqual(proficiency_bonus(1), 2)
        self.assertEqual(proficiency_bonus(5), 3)
        self.assertEqual(proficiency_bonus(9), 4)

    def test_ability_check_with_proficiency(self):
        result = ability_check(
            16,
            15,
            proficiency=True,
            level=1,
            rng=FixedRng([12]),
        )
        self.assertEqual(result.total, 15)
        self.assertTrue(result.success)

    def test_check_can_fail(self):
        result = ability_check(8, 15, rng=FixedRng([10]))
        self.assertEqual(result.total, 9)
        self.assertFalse(result.success)


class CharacterTests(unittest.TestCase):
    def test_character_has_core_state(self):
        character = Character(
            name="Kira",
            race="Elfa",
            class_name="Ladina",
            abilities={
                "Força": 10,
                "Destreza": 16,
                "Constituição": 12,
                "Inteligência": 10,
                "Sabedoria": 11,
                "Carisma": 13,
            },
            max_hp=10,
            hp=10,
            armor_class=14,
        )
        self.assertEqual(character.modifier("Destreza"), 3)
        self.assertEqual(character.proficiency_bonus, 2)
        self.assertTrue(character.is_alive())

    def test_engine_uses_character_proficiency(self):
        character = Character(
            name="Kira",
            race="Elfa",
            class_name="Ladina",
            abilities={ability: 10 for ability in (
                "Força", "Destreza", "Constituição",
                "Inteligência", "Sabedoria", "Carisma",
            )},
            proficient_abilities={"Destreza"},
            max_hp=8,
            hp=8,
            armor_class=12,
        )
        result = GameEngine().ability_check(
            character, "Destreza", 12, rng=FixedRng([10])
        )
        self.assertEqual(result.total, 12)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
