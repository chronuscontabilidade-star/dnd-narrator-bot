import unittest

from dnd_bot.game.character import Character
from dnd_bot.game.simulator import (
    CampaignSimulator,
    ScriptedPlayerAgent,
    build_vertical_slice_adventure,
)


class FixedRng:
    """RNG previsível: d20=10 e demais dados=4."""

    def randint(self, low, high):
        return 10 if high == 20 else 4


class CampaignSimulatorTests(unittest.TestCase):
    def test_vertical_slice_reaches_valid_desfecho(self):
        character = Character(
            name="Teste",
            race="Humano",
            class_name="Guerreiro",
            abilities={
                "Força": 16,
                "Destreza": 12,
                "Constituição": 14,
                "Inteligência": 14,
                "Sabedoria": 12,
                "Carisma": 10,
            },
            level=1,
            max_hp=20,
            hp=20,
            armor_class=15,
        )

        result = CampaignSimulator(rng=FixedRng()).run(
            build_vertical_slice_adventure(),
            character,
            agent=ScriptedPlayerAgent(),
            max_steps=10,
        )

        self.assertTrue(result.report.passed, result.report.failures)
        self.assertEqual(result.report.status, "concluida")
        self.assertGreaterEqual(result.report.checks, 2)
        self.assertEqual(result.report.combats, 1)
        self.assertEqual(result.report.quests_completed, 1)
        self.assertIn("beco", result.state.data["progresso"]["locais_descobertos"])
        self.assertIn("cripta", result.state.data["progresso"]["locais_visitados"])
        self.assertIn("quest_cinzas", result.state.data["progresso"]["quests_concluidas"])
        self.assertEqual(
            result.state.data["encounters"][0]["status"],
            "concluido",
        )

    def test_invalid_initial_campaign_is_reported(self):
        state = build_vertical_slice_adventure().to_dict()
        state["progresso"]["local_atual"] = "nao_existe"

        from dnd_bot.game.adventure import AdventureState

        result = CampaignSimulator().run(
            AdventureState.from_dict(state),
            Character(
                name="Teste",
                race="Humano",
                class_name="Guerreiro",
                max_hp=10,
                hp=10,
            ),
        )

        self.assertEqual(result.report.status, "falhou")
        self.assertTrue(result.report.failures)


if __name__ == "__main__":
    unittest.main()
