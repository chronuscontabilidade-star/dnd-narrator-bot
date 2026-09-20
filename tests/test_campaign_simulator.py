import unittest

from dnd_bot.game.adventure import AdventureState
from dnd_bot.game.character import Character
from dnd_bot.game.party import PartyDecision, PartyDecisionResolver, PartyVote
from dnd_bot.game.participation import PartyParticipation, PartyParticipationResolver
from dnd_bot.game.validator import AdventureValidator
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

    def test_simulator_resolves_quest_by_structured_targets_not_fixture_ids(self):
        state = build_vertical_slice_adventure().to_dict()
        state["aventura"]["id"] = "outra-aventura"
        state["quests"][0]["id"] = "quest_generica"
        state["quests"][0]["etapas"][0]["id"] = "etapa_local"
        state["quests"][0]["etapas"][0]["alvo"]["id"] = "beco"
        state["quests"][0]["etapas"][1]["id"] = "etapa_cripta"
        state["quests"][0]["etapas"][1]["alvo"]["id"] = "cripta"
        state["quests"][0]["etapas"][2]["id"] = "etapa_encounter"
        state["quests"][0]["etapas"][2]["alvo"]["id"] = "encontro_guardiao"

        result = CampaignSimulator(rng=FixedRng()).run(
            AdventureState.from_dict(state),
            Character(
                name="Teste",
                race="Humano",
                class_name="Guerreiro",
                abilities={
                    "Força": 16, "Destreza": 12, "Constituição": 14,
                    "Inteligência": 14, "Sabedoria": 12, "Carisma": 10,
                },
                max_hp=20,
                hp=20,
                armor_class=15,
            ),
            agent=ScriptedPlayerAgent(),
            max_steps=10,
        )

        self.assertTrue(result.report.passed, result.report.failures)
        self.assertIn("quest_generica", result.state.data["progresso"]["quests_concluidas"])

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


    def test_individual_participation_can_be_declined(self):
        resolution = PartyParticipationResolver().resolve(
            "decisao-1",
            "Investigar a cripta",
            (
                PartyParticipation("lia", "Investigar a cripta", True),
                PartyParticipation("bruno", "Investigar a cripta", False),
            ),
        )

        self.assertEqual([p.player_id for p in resolution.participants], ["lia"])
        self.assertEqual(resolution.declined, ("bruno",))
        self.assertIn("1 participante", resolution.reason)

    def test_individual_participation_rejects_duplicate_player(self):
        with self.assertRaises(ValueError):
            PartyParticipationResolver().resolve(
                "decisao-1",
                "Investigar",
                (
                    PartyParticipation("lia", "Investigar"),
                    PartyParticipation("lia", "Investigar"),
                ),
            )

    def test_party_report_records_individual_participation_metrics(self):
        state = build_vertical_slice_adventure()
        members = [
            PartyMember(
                Character(
                    name="Lia", race="Humano", class_name="Ladino",
                    abilities={
                        "Força": 10, "Destreza": 16, "Constituição": 12,
                        "Inteligência": 12, "Sabedoria": 16, "Carisma": 12,
                    },
                    max_hp=12, hp=12, armor_class=14,
                ),
                PersonalityPlayerAgent("social"),
            ),
            PartyMember(
                Character(
                    name="Bruno", race="Humano", class_name="Guerreiro",
                    abilities={
                        "Força": 16, "Destreza": 12, "Constituição": 14,
                        "Inteligência": 10, "Sabedoria": 12, "Carisma": 10,
                    },
                    max_hp=20, hp=20, armor_class=15,
                ),
                PersonalityPlayerAgent("cauteloso"),
            ),
        ]

        result = CampaignSimulator(rng=FixedRng()).run_party(
            state,
            members,
            max_rounds=10,
        )

        self.assertGreaterEqual(result.report.participation_rounds, 1)
        self.assertGreaterEqual(result.report.participants, 1)
        self.assertGreaterEqual(result.report.individual_results, 1)
        self.assertTrue(
            any(event.startswith("participacao:Lia:aceita:") for event in result.report.events)
        )


    def test_adventure_validator_detects_broken_references(self):
        state = build_vertical_slice_adventure().to_dict()
        state["locais"][0]["conexoes"].append("local_inexistente")
        state["npcs"][0]["local_atual"] = "local_inexistente"
        issues = AdventureValidator().validate(AdventureState.from_dict(state))
        codes = {issue.code for issue in issues}
        self.assertIn("broken_location_connection", codes)
        self.assertIn("broken_npc_location", codes)

    def test_simulator_rejects_invalid_campaign_before_running(self):
        state = build_vertical_slice_adventure().to_dict()
        state["locais"][0]["conexoes"].append("local_inexistente")
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
        self.assertTrue(
            any("broken_location_connection" in failure for failure in result.report.failures)
        )


    def test_adventure_validator_flags_unreachable_location_as_warning(self):
        state = build_vertical_slice_adventure().to_dict()
        state["locais"].append({
            "id": "torre_isolada",
            "nome": "Torre Isolada",
            "tipo": "outro",
            "descricao": "Uma torre sem acesso.",
            "descoberto": False,
            "visitado": False,
            "conexoes": [],
            "encontros": [],
        })
        issues = AdventureValidator().validate(AdventureState.from_dict(state))
        issue = next(item for item in issues if item.code == "unreachable_location")
        self.assertEqual(issue.severity, "warning")

    def test_adventure_validator_rejects_empty_quest(self):
        state = build_vertical_slice_adventure().to_dict()
        state["quests"][0]["etapas"] = []
        issues = AdventureValidator().validate(AdventureState.from_dict(state))
        self.assertIn("quest_without_steps", {issue.code for issue in issues})


    def test_adventure_validator_detects_broken_quest_location(self):
        state = build_vertical_slice_adventure().to_dict()
        state["quests"][0]["etapas"][0]["local_objetivo"] = "local_inexistente"
        issues = AdventureValidator().validate(AdventureState.from_dict(state))
        self.assertIn("broken_quest_location", {issue.code for issue in issues})

    def test_invalid_initial_campaign_is_reported(self):
        state = build_vertical_slice_adventure().to_dict()
        state["progresso"]["local_atual"] = "nao_existe"

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
