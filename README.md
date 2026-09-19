# D&D Narrator Bot

Bot de RPG D&D para Telegram, com criação guiada de personagens, regras de
atributos de D&D 5e, rolagens de dados, narrativa com IA e fallback offline.

## Executar

```powershell
cd dnd_bot
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python bot.py
```

Configure os tokens no `.env`. Para desenvolvimento, o banco usa SQLite em
`DATABASE_PATH` (padrão `dnd.db`). Em produção, defina
`SUPABASE_DB_URL` com uma URL Postgres do Supabase; ela tem prioridade sobre
`DATABASE_PATH`. Consulte [`dnd_bot/README.md`](dnd_bot/README.md) para as
opções de Gemini, Groq, OpenRouter, Ollama, proxy e implantação.

## Testes

```powershell
python -m unittest discover -s tests
```

## Roadmap de evolução

### Fase 0, estabilização
- [x] Corrigir bugs críticos da auditoria.
- [x] Adicionar testes de regressão.
- [x] Criar CI básico.
- [ ] Validar CI da branch.
- [ ] Revisar e fazer merge.

### Fase 1, GameEngine
- [ ] Separar estado do jogo da narrativa.
- [ ] Criar GameEngine como fonte de verdade.
- [ ] Mover regras determinísticas para módulos próprios.
- [ ] Implementar HP, CA, nível, XP e proficiências.
- [ ] Implementar inventário e recursos.
- [ ] Criar sistema de eventos.

### Fase 2, combate
- [ ] Iniciativa e turnos.
- [ ] Ação, ação bônus, reação e movimento.
- [ ] Ataques, dano e defesa.
- [ ] Condições.
- [ ] Morte e death saves.
- [ ] Monstros e NPCs estruturados.

### Fase 3, mundo persistente
- [ ] Campanhas separadas do chat.
- [ ] Jogadores vinculados a campanhas.
- [ ] NPCs persistentes.
- [ ] Locais e mapas.
- [ ] Quests.
- [ ] Fatos do mundo.
- [ ] Eventos históricos.
- [ ] Memória narrativa.

### Fase 4, Mestre de IA
- [ ] IA como intérprete e narrador, não autoridade sobre regras.
- [ ] Tool calling.
- [ ] Consulta estruturada ao GameEngine.
- [ ] Memória de longo prazo.
- [ ] Planejamento de cenas.
- [ ] NPCs com objetivos e personalidade.
- [ ] Continuidade de lore.

### Fase 5, multimídia
- [ ] Imagens de cena.
- [ ] Retratos.
- [ ] Mapas.
- [ ] Voz do Mestre.
- [ ] Áudio de personagens.
- [ ] Handouts.

### Fase 6, operação
- [ ] Logs estruturados.
- [ ] Métricas.
- [ ] Health check.
- [ ] Backup e restore.
- [ ] Controle de custos por provider.
- [ ] Rate limiting.
- [ ] Observabilidade.

## Princípio arquitetural

A IA narra e interpreta. O GameEngine decide e valida. O banco persiste.

O objetivo é impedir que uma resposta criativa do modelo altere arbitrariamente HP, inventário, regras, turnos ou estado da campanha.
