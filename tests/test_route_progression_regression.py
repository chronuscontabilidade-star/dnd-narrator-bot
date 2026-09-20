import unittest

from dnd_bot.game.action import ActionResolver
from dnd_bot.game.adventure import AdventureState
from dnd_bot.narrator import Narrator


class RouteProgressionRegressionTests(unittest.TestCase):
    def _adventure(self):
        return {
            "schema_version": 1,
            "aventura": {"id": "regressao", "titulo": "Teste", "resumo": "Teste", "status": "em_andamento"},
            "mundo": {},
            "locais": [
                {"id": "inicio", "nome": "Templo", "descoberto": True, "visitado": True, "conexoes": ["interno"]},
                {"id": "interno", "nome": "Área interna", "descoberto": False, "visitado": False, "conexoes": ["inicio", "profundo"]},
                {"id": "profundo", "nome": "Área profunda", "descoberto": False, "visitado": False, "conexoes": ["interno"]},
            ],
            "npcs": [],
            "encounters": [],
            "quests": [],
            "itens": [],
            "flags": {},
            "progresso": {
                "local_atual": "inicio",
                "locais_descobertos": ["inicio"],
                "locais_visitados": ["inicio"],
                "npcs_conhecidos": [],
                "encounters_concluidos": [],
                "quests_concluidas": [],
                "eventos_importantes": [],
                "etapa_cena": 0,
            },
        }

    def test_advancing_discovered_route_is_movement_with_next_destination(self):
        adventure = self._adventure()
        intent = ActionResolver(adventure).resolve("avançar pela rota descoberta")
        self.assertEqual(intent.tipo, "movimento")
        self.assertEqual(intent.destino, "interno")
        self.assertFalse(intent.requer_teste)

    def test_repeating_route_action_progresses_instead_of_repeating_same_scene(self):
        narrator = Narrator("")
        adventure = self._adventure()
        character = {"nome": "Robert", "classe": "Guerreiro", "raca": "Humano", "atributos": {}}
        narrativas = []

        for expected_location, expected_next in (("inicio", "interno"), ("interno", "profundo")):
            session = {
                "contexto": f"Localização atual: {expected_location}.",
                "aventura": adventure,
            }
            intent = ActionResolver(adventure).resolve("avançar pela rota descoberta")
            self.assertEqual(intent.tipo, "movimento")
            self.assertEqual(intent.destino, expected_next)

            resultado = narrator._fallback_narrativa(
                session, character, "avançar pela rota descoberta", None
            )
            narrativas.append(resultado["narrativa"])

            state = AdventureState.from_dict(adventure)
            state = state.update_progress(
                current_location=intent.destino,
                discovered_location=intent.destino,
                visited_location=intent.destino,
            )
            adventure = state.to_dict()

        self.assertEqual(adventure["progresso"]["local_atual"], "profundo")
        self.assertNotEqual(narrativas[0], narrativas[1])
        self.assertIn("Área interna", narrativas[0])
        self.assertIn("Área profunda", narrativas[1])

        # Terceira tentativa, já sem nova conexão, também não pode voltar
        # ao placeholder genérico observado no Telegram.
        session = {"contexto": "Localização atual: profundo.", "aventura": adventure}
        resultado_final = narrator._fallback_narrativa(
            session, character, "avançar pela rota descoberta", None
        )
        self.assertNotIn("a atenção agora se concentra", resultado_final["narrativa"].lower())
        self.assertIn("não encontra uma nova saída", resultado_final["narrativa"].lower())


if __name__ == "__main__":
    unittest.main()
