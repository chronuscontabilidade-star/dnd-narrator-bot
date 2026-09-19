import unittest

from dnd_bot.game.character import Character
from dnd_bot.game.party import PartyDecision, PartyDecisionResolver, PartyVote
from dnd_bot.game.simulator import (
    CampaignSimulator,
    GoalDrivenPlayerAgent,
    PartyMember,
    PersonalityPlayerAgent,
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
        self.assertGreaterEqual(len(result.report.director_levels), 1)
        self.assertEqual(result.report.loops_detected, 0)

    def test_goal_driven_agent_reads_campaign_state(self):
        state = build_vertical_slice_adventure()
        action = GoalDrivenPlayerAgent().choose_action(
            state,
            Character(name="Teste", race="Humano", class_name="Guerreiro"),
            0,
        )
        self.assertIn("investigar", action.lower())


    def test_party_simulator_shares_campaign_state_between_members(self):
        state = build_vertical_slice_adventure()
        members = [
            PartyMember(
                Character(
                    name="Lia",
                    race="Humano",
                    class_name="Ladino",
                    abilities={
                        "Força": 10, "Destreza": 16, "Constituição": 12,
                        "Inteligência": 12, "Sabedoria": 16, "Carisma": 12,
                    },
                    max_hp=12,
                    hp=12,
                    armor_class=14,
                ),
                PersonalityPlayerAgent("social"),
            ),
            PartyMember(
                Character(
                    name="Bruno",
                    race="Humano",
                    class_name="Guerreiro",
                    abilities={
                        "Força": 16, "Destreza": 12, "Constituição": 14,
                        "Inteligência": 10, "Sabedoria": 12, "Carisma": 10,
                    },
                    max_hp=20,
                    hp=20,
                    armor_class=15,
                ),
                ScriptedPlayerAgent(),
            ),
        ]

        result = CampaignSimulator(rng=FixedRng()).run_party(
            state,
            members,
            max_rounds=10,
        )

        self.assertTrue(result.report.passed, result.report.failures)
        self.assertEqual(result.report.status, "concluida")
        self.assertEqual(result.report.combats, 1)
        self.assertEqual(result.members, ["Lia", "Bruno"])
        self.assertTrue(
            any(event.startswith("jogador:Lia:acao:") for event in result.report.events)
        )
        self.assertIn(
            "quest_cinzas",
            result.state.data["progresso"]["quests_concluidas"],
        )


    def test_party_decision_requires_absolute_majority(self):
        decision = PartyDecision(
            id="decisao-1",
            prompt="O que a party faz?",
            options=("Investigar", "Conversar", "Sair"),
            reason="A cena está parada.",
        )
        resolution = PartyDecisionResolver().resolve(
            decision,
            (
                PartyVote("lia", "Investigar"),
                PartyVote("bruno", "Investigar"),
                PartyVote("caio", "Conversar"),
            ),
        )

        self.assertTrue(resolution.accepted)
        self.assertEqual(resolution.selected_option, "Investigar")
        self.assertEqual(resolution.executor_id, "lia")
        self.assertEqual(resolution.counts["Investigar"], 2)
        self.assertFalse(resolution.tied)

    def test_party_decision_tie_does_not_execute(self):
        decision = PartyDecision(
            id="decisao-empate",
            prompt="Qual caminho?",
            options=("Esquerda", "Direita"),
            reason="Dois caminhos possíveis.",
        )
        resolution = PartyDecisionResolver().resolve(
            decision,
            (
                PartyVote("lia", "Esquerda"),
                PartyVote("bruno", "Direita"),
            ),
        )

        self.assertFalse(resolution.accepted)
        self.assertIsNone(resolution.selected_option)
        self.assertIsNone(resolution.executor_id)
        self.assertTrue(resolution.tied)
        self.assertEqual(resolution.reason, "Empate: a decisão foi rejeitada sem alterar o estado.")

    def test_party_decision_rejects_duplicate_voter(self):
        decision = PartyDecision(
            id="decisao-duplicada",
            prompt="Escolha.",
            options=("A", "B"),
            reason="Teste.",
        )

        with self.assertRaises(ValueError):
            PartyDecisionResolver().resolve(
                decision,
                (
                    PartyVote("lia", "A"),
                    PartyVote("lia", "B"),
                ),
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
