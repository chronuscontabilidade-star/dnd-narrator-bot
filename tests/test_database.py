import tempfile
import unittest

from dnd_bot.database import Database


class CharacterCombatPersistenceTests(unittest.TestCase):
    def test_character_combat_stats_are_persisted_and_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(path=f"{tmp}/dnd.db")
            db.salvar_personagem(
                10, 20, "Kira", "Guerreiro", "Humano",
                {"Força": 14, "Destreza": 12, "Constituição": 14,
                 "Inteligência": 10, "Sabedoria": 10, "Carisma": 10},
                "história",
                "conceito",
                nivel=1,
                hp_max=12,
                hp=12,
                ca=11,
            )
            character = db.obter_personagem(10, 20)
            self.assertEqual(character["hp_max"], 12)
            self.assertEqual(character["hp"], 12)
            self.assertEqual(character["ca"], 11)

            self.assertTrue(db.atualizar_status_combate(10, 20, 5))
            updated = db.obter_personagem(10, 20)
            self.assertEqual(updated["hp"], 5)


if __name__ == "__main__":
    unittest.main()
