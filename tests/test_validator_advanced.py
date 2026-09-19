import unittest

from dnd_bot.game.adventure import AdventureState
from dnd_bot.game.simulator import build_vertical_slice_adventure
from dnd_bot.game.validator import AdventureValidator


class AdventureValidatorAdvancedTests(unittest.TestCase):
    def setUp(self):
        self.validator = AdventureValidator()

    def test_vertical_slice_has_viable_first_quest_target(self):
        state = build_vertical_slice_adventure()

        issues = self.validator.validate(state)

        errors = [issue for issue in issues if issue.severity == "error"]
        self.assertEqual([], errors)
        self.assertNotIn("quest_target_unreachable", {issue.code for issue in issues})

    def test_unreachable_quest_target_is_error(self):
        raw = build_vertical_slice_adventure().to_dict()
        raw["locais"][0]["conexoes"] = []

        state = AdventureState.from_dict(raw)
        issues = self.validator.validate(state)

        self.assertIn(
            "quest_target_unreachable",
            {issue.code for issue in issues},
        )

    def test_missing_encounter_quest_target_is_error(self):
        raw = build_vertical_slice_adventure().to_dict()
        raw["quests"][0]["etapas"][0]["alvo"] = {
            "tipo": "encounter",
            "id": "encounter_inexistente",
        }

        state = AdventureState.from_dict(raw)
        issues = self.validator.validate(state)

        self.assertIn("broken_quest_target", {issue.code for issue in issues})

    def test_item_without_location_or_carrier_has_no_acquisition_path(self):
        raw = build_vertical_slice_adventure().to_dict()
        raw["itens"] = [
            {
                "id": "chave_antiga",
                "nome": "Chave Antiga",
                "tipo": "quest",
                "local_atual": None,
                "portador": None,
                "importante": True,
            }
        ]
        raw["quests"][0]["etapas"][0]["alvo"] = {
            "tipo": "item",
            "id": "chave_antiga",
        }

        state = AdventureState.from_dict(raw)
        issues = self.validator.validate(state)

        self.assertIn(
            "quest_item_without_acquisition_path",
            {issue.code for issue in issues},
        )

    def test_npc_target_uses_npc_location_for_reachability(self):
        raw = build_vertical_slice_adventure().to_dict()
        raw["npcs"].append(
            {
                "id": "eremita",
                "nome": "Eremita",
                "funcao": "informante",
                "local_atual": "cripta",
                "descricao": "",
                "motivacao": "",
                "informacoes": [],
                "segredos": [],
                "vivo": True,
            }
        )
        raw["quests"][0]["etapas"][0]["alvo"] = {
            "tipo": "npc",
            "id": "eremita",
        }

        state = AdventureState.from_dict(raw)
        issues = self.validator.validate(state)

        self.assertNotIn(
            "quest_target_unreachable",
            {issue.code for issue in issues},
        )

    def test_active_quest_without_pending_steps_is_error(self):
        raw = build_vertical_slice_adventure().to_dict()
        for step in raw["quests"][0]["etapas"]:
            step["status"] = "concluida"

        state = AdventureState.from_dict(raw)
        issues = self.validator.validate(state)

        self.assertIn(
            "active_quest_without_pending_steps",
            {issue.code for issue in issues},
        )


if __name__ == "__main__":
    unittest.main()
