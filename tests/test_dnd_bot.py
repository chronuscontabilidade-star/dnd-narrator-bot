import asyncio
import tempfile
import unittest
from pathlib import Path

from dnd_bot.database import Database
from dnd_bot.game.adventure import AdventureState, SCHEMA_VERSION, adventure_generation_prompt
from dnd_bot.dice import realizar_teste
from dnd_bot.narrator import Narrator
from dnd_bot.game.action import ActionResolver, movimento_permitido


class NarratorTests(unittest.TestCase):
    def test_offline_narrator_starts_structured_adventure(self):
        intro = asyncio.run(Narrator("").iniciar_aventura(123))
        state = AdventureState.from_dict(intro)
        self.assertEqual(state.data["schema_version"], SCHEMA_VERSION)
        self.assertTrue(state.data["aventura"]["titulo"])
        self.assertTrue(state.data["locais"])
        self.assertTrue(state.data["progresso"]["local_atual"])
        self.assertTrue(intro["narrativa"])
        self.assertTrue(intro["contexto"])

    def test_adventure_state_transitions(self):
        raw = {
            "schema_version": 1,
            "aventura": {"id": "a", "titulo": "A", "resumo": "R", "status": "em_andamento"},
            "mundo": {}, "locais": [
                {"id": "inicio", "nome": "Inicio", "descoberto": True, "visitado": True, "conexoes": ["cripta"]},
                {"id": "cripta", "nome": "Cripta", "descoberto": False, "visitado": False, "conexoes": []},
            ],
            "npcs": [], "encounters": [], "quests": [], "itens": [], "flags": {},
            "progresso": {"local_atual": "inicio", "locais_descobertos": ["inicio"],
                          "locais_visitados": ["inicio"], "npcs_conhecidos": [],
                          "encounters_concluidos": [], "quests_concluidas": [], "eventos_importantes": []},
        }
        state = AdventureState.from_dict(raw)
        state = state.update_progress(current_location="cripta", discovered_location="cripta", visited_location="cripta")
        self.assertEqual(state.data["progresso"]["local_atual"], "cripta")
        self.assertIn("cripta", state.data["progresso"]["locais_descobertos"])
        self.assertTrue(next(x for x in state.data["locais"] if x["id"] == "cripta")["visitado"])

    def test_adventure_state_rejects_unknown_references(self):
        raw = {
            "schema_version": 1,
            "aventura": {"id": "a", "titulo": "A", "resumo": "R", "status": "em_andamento"},
            "mundo": {}, "locais": [{"id": "inicio", "nome": "Inicio", "descoberto": True, "visitado": True, "conexoes": []}],
            "npcs": [], "encounters": [{"id": "enc1", "status": "pendente"}],
            "quests": [{"id": "q1", "status": "ativa", "etapas": [{"id": "s1", "status": "pendente"}]}],
            "itens": [], "flags": {}, "segredos": [{"id": "seg1", "revelado": False}],
            "progresso": {"local_atual": "inicio", "locais_descobertos": ["inicio"],
                          "locais_visitados": ["inicio"], "npcs_conhecidos": [],
                          "encounters_concluidos": [], "quests_concluidas": [], "eventos_importantes": []},
        }
        state = AdventureState.from_dict(raw)
        with self.assertRaises(ValueError):
            state.update_progress(current_location="fantasma")
        with self.assertRaises(ValueError):
            state.reveal_secret("seg-inexistente")
        with self.assertRaises(ValueError):
            state.complete_encounter("enc-inexistente")
        with self.assertRaises(ValueError):
            state.complete_quest_step("q-inexistente", "s1")
        with self.assertRaises(ValueError):
            state.complete_quest_step("q1", "s-inexistente")

    def test_secret_reveal_updates_progress(self):
        raw = {
            "schema_version": 1,
            "aventura": {"id": "a", "titulo": "A", "resumo": "R", "status": "em_andamento"},
            "mundo": {}, "locais": [{"id": "inicio", "nome": "Inicio", "descoberto": True, "visitado": True, "conexoes": []}],
            "npcs": [], "encounters": [], "quests": [], "itens": [],
            "flags": {}, "segredos": [{"id": "seg1", "revelado": False}],
            "progresso": {"local_atual": "inicio", "locais_descobertos": ["inicio"],
                          "locais_visitados": ["inicio"], "npcs_conhecidos": [],
                          "encounters_concluidos": [], "quests_concluidas": [], "eventos_importantes": []},
        }
        state = AdventureState.from_dict(raw).reveal_secret("seg1")
        self.assertTrue(state.data["segredos"][0]["revelado"])
        self.assertEqual(state.data["progresso"]["segredos_revelados"], ["seg1"])

    def test_quest_steps_cannot_skip_previous_step(self):
        raw = {
            "schema_version": 1,
            "aventura": {"id": "a", "titulo": "A", "resumo": "R", "status": "em_andamento"},
            "mundo": {}, "locais": [{"id": "inicio", "nome": "Inicio", "descoberto": True, "visitado": True, "conexoes": []}],
            "npcs": [], "encounters": [], "quests": [{
                "id": "q1", "status": "ativa",
                "etapas": [
                    {"id": "s1", "status": "pendente"},
                    {"id": "s2", "status": "pendente"},
                ],
            }],
            "itens": [], "flags": {}, "segredos": [],
            "progresso": {"local_atual": "inicio", "locais_descobertos": ["inicio"],
                          "locais_visitados": ["inicio"], "npcs_conhecidos": [],
                          "encounters_concluidos": [], "quests_concluidas": [], "eventos_importantes": []},
        }
        state = AdventureState.from_dict(raw)
        with self.assertRaises(ValueError):
            state.complete_quest_step("q1", "s2")

    def test_adventure_state_rejects_unsupported_schema_version(self):
        raw = {
            "schema_version": 999,
            "aventura": {"id": "a", "titulo": "A", "resumo": "R", "status": "em_andamento"},
            "mundo": {}, "locais": [], "npcs": [], "encounters": [], "quests": [],
            "itens": [], "flags": {}, "progresso": {},
        }
        with self.assertRaises(ValueError):
            AdventureState.from_dict(raw)

    def test_end_turn_intent_is_not_a_skill_check(self):
        intent = ActionResolver({"combate": {"combatants": []}}).resolve("encerrar turno")
        self.assertEqual(intent.tipo, "fim_turno")
        self.assertFalse(intent.requer_teste)

    def test_attack_intent_targets_active_combatant(self):
        adventure = {
            "combate": {
                "combatants": [
                    {"name": "Kira"},
                    {"name": "Goblin Rei"},
                ]
            }
        }
        intent = ActionResolver(adventure).resolve("atacar Goblin Rei")
        self.assertEqual(intent.tipo, "ataque")
        self.assertEqual(intent.alvo, "Goblin Rei")
        self.assertFalse(intent.requer_teste)

    def test_attack_intent_does_not_invent_target(self):
        intent = ActionResolver({"combate": {"combatants": [{"name": "Goblin"}]}}).resolve("atacar o dragão")
        self.assertEqual(intent.tipo, "ataque")
        self.assertIsNone(intent.alvo)

    def test_movement_does_not_teleport_to_discovered_location(self):
        raw = {
            "schema_version": 1,
            "aventura": {"id": "a", "titulo": "A", "resumo": "R", "status": "em_andamento"},
            "mundo": {}, "locais": [
                {"id": "inicio", "nome": "Inicio", "descoberto": True, "visitado": True, "conexoes": ["sala"]},
                {"id": "sala", "nome": "Sala", "descoberto": True, "visitado": True, "conexoes": ["inicio"]},
                {"id": "longe", "nome": "Longe", "descoberto": True, "visitado": True, "conexoes": []},
            ],
            "npcs": [], "encounters": [], "quests": [], "itens": [], "flags": {}, "segredos": [],
            "progresso": {"local_atual": "inicio", "locais_descobertos": ["inicio", "sala", "longe"],
                          "locais_visitados": ["inicio", "sala", "longe"], "npcs_conhecidos": [],
                          "encounters_concluidos": [], "quests_concluidas": [], "eventos_importantes": []},
        }
        state = AdventureState.from_dict(raw)
        self.assertTrue(movimento_permitido(state.to_dict(), "sala"))
        self.assertFalse(movimento_permitido(state.to_dict(), "longe"))

    def test_adventure_generation_prompt_defines_stable_contract(self):
        prompt = adventure_generation_prompt()
        self.assertIn('"schema_version": 1', prompt)
        self.assertIn('"locais"', prompt)
        self.assertIn('"npcs"', prompt)
        self.assertIn('"quests"', prompt)
        self.assertIn('"progresso"', prompt)

    def test_json_parser_accepts_markdown_fence(self):
        parsed = Narrator("")._parse_json("```json\n{\"ok\": true}\n```")
        self.assertEqual(parsed, {"ok": True})

    def test_offline_adventure_has_a_navigable_fallback_map(self):
        intro = asyncio.run(Narrator("").iniciar_aventura(321))
        locais = {local["id"]: local for local in intro["locais"]}
        self.assertIn("local_inicial", locais)
        self.assertIn("area_interna", locais)
        self.assertIn("area_profunda", locais)
        self.assertIn("area_interna", locais["local_inicial"]["conexoes"])
        self.assertIn("area_profunda", locais["area_interna"]["conexoes"])
        self.assertEqual(intro["progresso"]["local_atual"], "local_inicial")
        self.assertEqual(intro["progresso"]["etapa_cena"], 0)

    def test_offline_narration_changes_beat_instead_of_repeating_same_scene(self):
        narrator = Narrator("")
        session = {
            "contexto": "Localização: Farol Antigo. Ameaça: ruínas despertas.",
            "aventura": {
                "progresso": {"local_atual": "local_inicial", "etapa_cena": 0, "eventos_importantes": []},
                "locais": [
                    {"id": "local_inicial", "nome": "Farol Antigo", "descricao": "Entrada do farol.", "conexoes": ["area_interna"]},
                    {"id": "area_interna", "nome": "Área interna", "descricao": "Corredor interno.", "conexoes": ["local_inicial", "area_profunda"]},
                    {"id": "area_profunda", "nome": "Área profunda", "descricao": "Parte profunda.", "conexoes": ["area_interna"]},
                ],
            },
        }
        character = {"nome": "Joelson", "classe": "Guerreiro", "raca": "Humano", "atributos": {"Inteligência": 10}}
        first = narrator._fallback_narrativa(session, character, "rastrear pegadas", None)
        session["contexto"] = first["novo_contexto"]
        session["aventura"]["progresso"]["etapa_cena"] = 1
        second = narrator._fallback_narrativa(session, character, "entrar no farol", None)
        self.assertNotEqual(first["narrativa"], second["narrativa"])
        self.assertIn("área interna", second["narrativa"].lower())
        self.assertIn("etapa 2", second["novo_contexto"].lower())

    def test_offline_action_advances_context_and_scene(self):
        narrator = Narrator("")
        session = {"contexto": "Localização: Farol Antigo. Ameaça: ruínas despertas."}
        character = {
            "nome": "Kira",
            "classe": "Ladina",
            "raca": "Elfa",
            "atributos": {"Destreza": 16},
        }
        result = asyncio.run(narrator.narrar_acao_com_dado(session, character, [character], "examino as pegadas", None))
        self.assertIn("examino as pegadas", result["novo_contexto"])
        self.assertIn("Resultado:", result["novo_contexto"])
        scene = asyncio.run(narrator.gerar_cena({"contexto": result["novo_contexto"]}))
        self.assertIn("Farol Antigo", scene["descricao"])

    def test_simple_actions_do_not_require_dice(self):
        narrator = Narrator("")
        session = {"contexto": "Localização: Farol Antigo. Ameaça: ruínas."}
        for action in ("caminho até a entrada", "avanço até o balcão", "se aproximar andando lentamente", "aproximar-se da porta"):
            with self.subTest(action=action):
                result = asyncio.run(narrator.avaliar_acao(session, action))
                self.assertFalse(result["precisa_teste"])

    def test_provider_quota_enters_cooldown(self):
        narrator = Narrator("")
        narrator._cooldown_provider("alternate", RuntimeError("HTTP 429 quota exceeded"))
        self.assertFalse(narrator._provider_available("alternate"))

    def test_suggestions_follow_current_scene(self):
        narrator = Narrator("")
        session = {"contexto": "Localização: balcão do Farol. Ameaça: inimigos imobilizados. Objetivo: dispersar os inimigos. Progressão: ação 3 concluída."}
        character = {"nome": "Artheal", "classe": "Mago", "raca": "Elfo", "atributos": {"Inteligência": 16, "Destreza": 14}}
        result = asyncio.run(narrator.sugerir_acoes(session, character))
        actions = " ".join(item["acao"] for item in result["sugestoes"])
        self.assertIn("inimigos", actions)
        self.assertIn("balcão", actions)

    def test_character_details_shape_offline_fallback(self):
        ficha = asyncio.run(Narrator("").criar_personagem("Kira", "Ladina", "Elfo", "coleciona chaves e teme espaços fechados"))
        self.assertIn("coleciona chaves", ficha["historia"])


class DiceTests(unittest.TestCase):
    def test_attribute_modifier_and_result_shape(self):
        result = realizar_teste({"Força": 14}, "Força", dificuldade=10)
        self.assertEqual(result["modificador"], 2)
        self.assertIn("sucesso", result)
        self.assertEqual(len(result["dados_rolados"]), 1)


class DatabaseTests(unittest.TestCase):
    def test_session_and_character_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "test.db"))
            database.criar_sessao(1, "contexto")
            database.salvar_personagem(2, 1, "Kira", "Ladina", "Elfica", {"Destreza": 16}, "historia", "ladina reservada; coleciona chaves")
            self.assertEqual(database.obter_sessao(1)["contexto"], "contexto")
            adventure = {"schema_version": 1, "aventura": {"id": "teste"}}
            self.assertTrue(database.atualizar_aventura(1, adventure))
            self.assertEqual(database.obter_sessao(1)["aventura"], adventure)
            self.assertEqual(database.obter_personagem(2, 1)["atributos"], {"Destreza": 16})

    def test_public_operations_and_new_session_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "test.db"))
            database.criar_sessao(1, "primeiro")
            database.salvar_personagem(2, 1, "Kira", "Ladina", "Elfica", {"Destreza": 16}, "historia")
            database.registrar_acao(2, 1, "explorar", "Encontrou uma porta")
            database.atualizar_contexto(1, "contexto atualizado")
            self.assertEqual(database.obter_sessao(1)["contexto"], "contexto atualizado")
            self.assertEqual(len(database.listar_jogadores(1)), 1)
            self.assertEqual(database.historico_recente(1)[0]["acao"], "explorar")
            database.criar_sessao(1, "segundo")
            self.assertEqual(len(database.listar_jogadores(1)), 1)
            self.assertEqual(database.historico_recente(1)[0]["acao"], "explorar")

    def test_ai_evaluation_validation(self):
        narrator = Narrator("")
        valid = narrator._validar_avaliacao({"precisa_teste": True, "atributo": "Força", "cd": "99"})
        self.assertEqual(valid["cd"], 30)
        self.assertEqual(valid["atributo"], "Força")
        with self.assertRaises(ValueError):
            narrator._validar_avaliacao({"precisa_teste": "false"})

    def test_character_sheet_validation_has_all_attributes(self):
        narrator = Narrator("")
        ficha = narrator._validar_ficha({"atributos": {"Força": 40, "Destreza": "x"}, "historia": "hist"})
        self.assertEqual(ficha["atributos"]["Força"], 30)
        self.assertEqual(ficha["atributos"]["Destreza"], 10)
        self.assertEqual(set(ficha["atributos"]), {"Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"})

    def test_character_details_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "test.db"))
            database.criar_sessao(1, "aventura")
            database.salvar_personagem(
                2, 1, "Kira", "Ladina", "Elfa",
                {"Destreza": 16}, "historia", "profissão: batedora; mania: colecionar chaves"
            )
            personagem = database.obter_personagem(2, 1)
            self.assertEqual(personagem["detalhes"], "profissão: batedora; mania: colecionar chaves")

    def test_two_players_survive_join(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "test.db"))
            database.criar_sessao(1, "aventura")
            database.salvar_personagem(10, 1, "Kira", "Ladina", "Elfa", {"Destreza": 16}, "h1")
            database.salvar_personagem(20, 1, "Thorin", "Guerreiro", "Anão", {"Força": 16}, "h2")
            database.criar_sessao(1, "aventura ainda ativa")
            self.assertEqual({p["nome"] for p in database.listar_jogadores(1)}, {"Kira", "Thorin"})

    def test_action_lock_serializes_same_chat(self):
        from dnd_bot.bot import action_locks

        class App:
            bot_data = {}

        class Ctx:
            application = App()

        ctx = Ctx()
        locks = action_locks(ctx)
        first = locks.setdefault(123, asyncio.Lock())
        second = locks.setdefault(123, asyncio.Lock())
        other = locks.setdefault(456, asyncio.Lock())
        self.assertIs(first, second)
        self.assertIsNot(first, other)

    def test_campaign_state_update_is_atomic_and_uses_cas(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "test.db"))
            database.criar_sessao(1, "A", aventura={"stage": 0})
            self.assertTrue(
                database.atualizar_estado_campanha(
                    1, "B", {"stage": 1}, contexto_anterior="A"
                )
            )
            session = database.obter_sessao(1)
            self.assertEqual(session["contexto"], "B")
            self.assertEqual(session["aventura"], {"stage": 1})
            self.assertFalse(
                database.atualizar_estado_campanha(
                    1, "C", {"stage": 2}, contexto_anterior="A"
                )
            )
            session = database.obter_sessao(1)
            self.assertEqual(session["contexto"], "B")
            self.assertEqual(session["aventura"], {"stage": 1})

    def test_context_compare_and_set_rejects_stale_update(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(str(Path(directory) / "test.db"))
            database.criar_sessao(1, "A")
            self.assertTrue(database.atualizar_contexto(1, "B", contexto_anterior="A"))
            self.assertFalse(database.atualizar_contexto(1, "C", contexto_anterior="A"))
            self.assertEqual(database.obter_sessao(1)["contexto"], "B")


if __name__ == "__main__":
    unittest.main()
