import asyncio
import unittest

from dnd_bot.game.action import ActionResolver
from dnd_bot.narrator import Narrator


class SemanticIntentTests(unittest.TestCase):
    def setUp(self):
        self.adventure = {
            "progresso": {"local_atual": "inicio"},
            "locais": [
                {"id": "inicio", "nome": "Templo", "descoberto": True, "conexoes": ["corredor"]},
                {"id": "corredor", "nome": "Corredor", "descoberto": False, "conexoes": ["inicio"]},
            ],
            "quests": [],
        }

    def test_ai_semantic_parser_maps_free_language_to_movement(self):
        narrator = Narrator("")

        async def fake_request(_prompt):
            return {
                "tipo": "movimento",
                "destino": None,
                "alvo": None,
                "habilidade": None,
                "referencia": "caminho das pegadas",
            }

        narrator._request_json = fake_request
        session = {"aventura": self.adventure, "contexto": "No templo."}
        result = asyncio.run(
            narrator.interpretar_acao(
                session,
                {"nome": "Kira", "classe": "Ladina", "raca": "Elfa"},
                "vou seguindo o caminho que as pegadas fizeram",
            )
        )

        self.assertEqual(result["tipo"], "movimento")
        self.assertIsNone(result["destino"])
        self.assertEqual(result["referencia"], "caminho das pegadas")

        intent = ActionResolver(self.adventure).resolve_semantic(
            "vou seguindo o caminho que as pegadas fizeram", result
        )
        self.assertEqual(intent.tipo, "movimento")
        self.assertFalse(intent.requer_teste)
        self.assertEqual(intent.destino, "corredor")

    def test_semantic_parser_cannot_invent_unknown_destination(self):
        narrator = Narrator("")
        narrator._request_json = lambda _prompt: asyncio.sleep(0, result={
            "tipo": "movimento",
            "destino": "castelo_inventado",
            "alvo": None,
            "habilidade": None,
            "referencia": "castelo",
        })
        session = {"aventura": self.adventure, "contexto": "No templo."}

        result = asyncio.run(
            narrator.interpretar_acao(
                session,
                {"nome": "Kira", "classe": "Ladina", "raca": "Elfa"},
                "vou para o castelo",
            )
        )

        self.assertIsNone(result["destino"])

    def test_semantic_bridge_keeps_mechanics_deterministic(self):
        intent = ActionResolver(self.adventure).resolve_semantic(
            "eu tento convencer o guarda a me deixar passar",
            {
                "tipo": "social",
                "alvo": "guarda",
                "habilidade": "Persuasão",
            },
        )
        self.assertEqual(intent.tipo, "social")
        self.assertEqual(intent.atributo, "Carisma")
        self.assertEqual(intent.cd, 12)
        self.assertTrue(intent.requer_teste)


if __name__ == "__main__":
    unittest.main()
