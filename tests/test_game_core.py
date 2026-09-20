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

    def test_invalid_die_and_quantity_are_rejected(self):
        with self.assertRaises(ValueError):
            roll(1, 1, FixedRng([1]))
        with self.assertRaises(ValueError):
            roll(6, 0, FixedRng([]))

    def test_invalid_dice_expression_is_rejected(self):
        with self.assertRaises(ValueError):
            roll_expression("2d6+")
        with self.assertRaises(ValueError):
            roll_expression("0d6")

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
        self.assertEqual(result.total, 17)
        self.assertTrue(result.success)

    def test_rules_reject_invalid_dc_and_level(self):
        with self.assertRaises(ValueError):
            ability_check(10, 0, rng=FixedRng([10]))
        with self.assertRaises(ValueError):
            ability_check(10, 31, rng=FixedRng([10]))
        with self.assertRaises(ValueError):
            proficiency_bonus(0)
        with self.assertRaises(ValueError):
            proficiency_bonus(21)

    def test_check_can_fail(self):
        result = ability_check(8, 15, rng=FixedRng([10]))
        self.assertEqual(result.total, 9)
        self.assertFalse(result.success)


class CharacterTests(unittest.TestCase):
    def test_character_rejects_invalid_hp_and_level(self):
        abilities = {ability: 10 for ability in (
            "Força", "Destreza", "Constituição",
            "Inteligência", "Sabedoria", "Carisma",
        )}
        with self.assertRaises(ValueError):
            Character("Kira", "Humano", "Guerreiro", abilities, level=0, max_hp=10, hp=10, armor_class=10)
        with self.assertRaises(ValueError):
            Character("Kira", "Humano", "Guerreiro", abilities, max_hp=10, hp=11, armor_class=10)
        with self.assertRaises(ValueError):
            Character("Kira", "Humano", "Guerreiro", abilities, max_hp=0, hp=0, armor_class=10)

    def test_character_rejects_invalid_identity_and_attributes(self):
        abilities = {ability: 10 for ability in (
            "Força", "Destreza", "Constituição",
            "Inteligência", "Sabedoria", "Carisma",
        )}
        with self.assertRaises(ValueError):
            Character("", "Humano", "Guerreiro", abilities, max_hp=10, hp=10, armor_class=10)
        with self.assertRaises(ValueError):
            Character("Kira", "Humano", "Guerreiro", {**abilities, "Luck": 10}, max_hp=10, hp=10, armor_class=10)
        with self.assertRaises(TypeError):
            Character("Kira", "Humano", "Guerreiro", {**abilities, "Força": True}, max_hp=10, hp=10, armor_class=10)
        with self.assertRaises(ValueError):
            Character("Kira", "Humano", "Guerreiro", abilities, proficient_abilities={"Luck"}, max_hp=10, hp=10, armor_class=10)

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


class CharacterCreationRulesTests(unittest.TestCase):
    def test_roll_4d6_drop_lowest(self):
        from dnd_bot.game.character_creation import rolar_atributo

        class FixedRng:
            values = iter([6, 5, 4, 1])

            def randint(self, _a, _b):
                return next(self.values)

        total, dice = rolar_atributo(FixedRng())
        self.assertEqual(dice, [6, 5, 4, 1])
        self.assertEqual(total, 15)

    def test_race_bonuses_are_applied_without_class_bonuses(self):
        from dnd_bot.game.character_creation import aplicar_bonuses_raciais

        base = {
            "Força": 15, "Destreza": 14, "Constituição": 13,
            "Inteligência": 12, "Sabedoria": 10, "Carisma": 8,
        }
        result = aplicar_bonuses_raciais(base, "Meio-Orc")
        self.assertEqual(result["Força"], 17)
        self.assertEqual(result["Constituição"], 14)
        self.assertEqual(result["Destreza"], 14)
        self.assertEqual(result["Inteligência"], 12)

    def test_generated_character_has_real_ability_modifiers(self):
        from dnd_bot.game.character_creation import gerar_atributos

        class FixedRng:
            values = iter([6, 6, 6, 1] * 6)

            def randint(self, _a, _b):
                return next(self.values)

        result = gerar_atributos("Guerreiro", "Humano", FixedRng())
        self.assertEqual(set(result), {"Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"})
        self.assertEqual(result["Força"], 19)
        self.assertTrue(any((value - 10) // 2 != 0 for value in result.values()))


class ActionResolverTests(unittest.TestCase):
    def setUp(self):
        self.adventure = {
            "locais": [
                {"id": "inicio", "nome": "Taverna do Corvo", "descoberto": True, "conexoes": ["cripta"]},
                {"id": "cripta", "nome": "Cripta Antiga", "descoberto": False, "conexoes": ["inicio"]},
            ]
        }

    def test_explorar_uses_investigacao(self):
        from dnd_bot.game.action import ActionResolver
        intent = ActionResolver(self.adventure).resolve("explorar a passagem")
        self.assertEqual(intent.tipo, "investigacao")
        self.assertEqual(intent.habilidade, "Investigação")
        self.assertEqual(intent.atributo, "Inteligência")
        self.assertTrue(intent.requer_teste)

    def test_enter_known_destination_is_movement_without_roll(self):
        from dnd_bot.game.action import ActionResolver
        intent = ActionResolver(self.adventure).resolve("entrar na Cripta Antiga")
        self.assertEqual(intent.tipo, "movimento")
        self.assertEqual(intent.destino, "cripta")
        self.assertFalse(intent.requer_teste)

    def test_observe_is_routine(self):
        from dnd_bot.game.action import ActionResolver
        intent = ActionResolver(self.adventure).resolve("observar")
        self.assertEqual(intent.tipo, "narrativa")
        self.assertFalse(intent.requer_teste)

    def test_listen_uses_perception(self):
        from dnd_bot.game.action import ActionResolver
        intent = ActionResolver(self.adventure).resolve("tentar ouvir se tem alguém atrás da porta")
        self.assertEqual(intent.tipo, "percepcao")
        self.assertEqual(intent.habilidade, "Percepção")
        self.assertEqual(intent.atributo, "Sabedoria")
        self.assertTrue(intent.requer_teste)

    def test_force_door_uses_athletics(self):
        from dnd_bot.game.action import ActionResolver
        intent = ActionResolver(self.adventure).resolve("arrombar a porta")
        self.assertEqual(intent.habilidade, "Atletismo")
        self.assertEqual(intent.atributo, "Força")
        self.assertTrue(intent.requer_teste)

    def test_social_action_maps_to_skill(self):
        from dnd_bot.game.action import ActionResolver
        intent = ActionResolver(self.adventure).resolve("persuadir o taverneiro")
        self.assertEqual(intent.habilidade, "Persuasão")
        self.assertEqual(intent.atributo, "Carisma")
        self.assertTrue(intent.requer_teste)

    def test_steal_maps_to_sleight_of_hand(self):
        from dnd_bot.game.action import ActionResolver
        intent = ActionResolver(self.adventure).resolve("tentar furtar a chave")
        self.assertEqual(intent.habilidade, "Prestidigitação")
        self.assertEqual(intent.atributo, "Destreza")
        self.assertTrue(intent.requer_teste)


if __name__ == "__main__":
    unittest.main()
