# D&D Narrator Bot

Bot de RPG para Telegram baseado em **D&D 5e 2014**, com narrativa generativa, regras determinísticas, campanhas estruturadas e fallback offline.

## 📍 Estado atual

O projeto está em **estabilização do primeiro núcleo jogável**.

A branch de trabalho desta rodada foi `fix/stability-audit-2026-09`. Ela concentrou a auditoria de estabilidade do fluxo real no Telegram, especialmente:

- criação de personagem;
- criação e retomada de aventura;
- persistência da sessão;
- interpretação de ações;
- testes de atributo/perícia;
- narrativa após ações;
- atualização de contexto;
- proteção contra teleporte/invenção de destinos;
- fallback determinístico quando a IA falha;
- providers Gemini, OpenAI-compatible/Bastião e fallback offline;
- comunicação segura com Telegram.

### O que já funciona no núcleo atual

- criação guiada de personagens;
- geração de atributos com 4d6, descartando o menor;
- bônus raciais das raças oferecidas;
- ficha inicial com conceito/história;
- AdventureState estruturado;
- geração e validação estruturada de aventuras;
- ActionResolver determinístico;
- testes básicos de atributos/perícias;
- persistência inicial de sessão e AdventureState;
- CAS para atualização de contexto;
- combate determinístico inicial;
- iniciativa, turnos, movimento, ataques, dano, crítico, Dash, Dodge e Disengage;
- SceneDirector;
- decisões/votações multiplayer;
- CampaignSimulator;
- providers com fallback;
- timeout real de requisições de IA;
- narrativa com validação e fallback offline;
- histórico recente e jogadores incluídos no contexto narrativo;
- registro de ações no progresso da aventura;
- movimento validado por conexões do grafo;
- proteção narrativa contra destinos desconhecidos sendo tratados como teleporte;
- reconhecimento de comandos informais de movimento, como `ir pra`, `vou pra`, `seguir pra` e `voltar pra`.

## 🧪 Último teste manual

O fluxo já chegou ao ponto de o bot produzir uma consequência narrativa concreta para uma ação simples como:

`/acao olhar ao redor`

Em vez do antigo placeholder, a resposta passou a acrescentar um detalhe observável à cena e sugerir próximos passos.

Também foi identificado um problema importante durante o teste:

`/acao ir pra cidade mais proxima procurar uma taverna`

era interpretado como investigação por causa da palavra "procurar". O resolver foi ajustado para reconhecer primeiro os padrões explícitos de movimento.

**Esse ajuste ainda precisa ser confirmado no próximo teste manual.**

Outro requisito foi reforçado: se o destino não existir como local conhecido/conectado, o personagem não pode simplesmente aparecer nele. A ação deve ser tratada como tentativa de viagem até que o caminho/destino seja validado.

## ⚠️ Ponto crítico ainda aberto

O próximo teste deve verificar **concorrência de ações no mesmo chat**.

O banco possui CAS para evitar sobrescrita cega de contexto, mas a camada Telegram ainda deve ser revisada para garantir serialização de ações por campanha/chat. Uma trava por `chat_id` é uma das próximas correções recomendadas antes de testes multiplayer agressivos.

Também é necessário verificar se uma resposta atrasada de provider pode devolver narrativa baseada em contexto anterior.

## Arquitetura

O princípio central é:

```
Jogador
  ↓
Telegram
  ↓
ActionResolver
  ↓
Intentão estruturada
  ↓
Regra/teste determinístico
  ↓
GameEngine / AdventureState
  ↓
Narrador IA ou fallback
  ↓
Novo estado/contexto
  ↓
Persistência
```

**Regra:** a IA narra e interpreta. O código decide, valida e aplica. O banco persiste.

## Componentes

- `dnd_bot/bot.py`: integração Telegram e fluxo da partida.
- `dnd_bot/narrator.py`: providers, geração narrativa, criação de personagens e fallback.
- `dnd_bot/database.py`: persistência.
- `dnd_bot/game/action.py`: interpretação determinística das ações.
- `dnd_bot/game/adventure.py`: estado estruturado da aventura.
- `dnd_bot/game/engine.py`: aplicação de regras.
- `dnd_bot/game/combat.py`: combate.
- `dnd_bot/game/director.py`: Diretor de Cena.
- `dnd_bot/game/party.py` e `participation.py`: decisões e participação multiplayer.
- `dnd_bot/game/validator.py`: validação do mundo/aventura.
- `dnd_bot/game/simulator.py`: simulação determinística.
- `tests/`: regressões automatizadas.
- `.github/workflows/tests.yml`: CI.

## Providers

A cadeia atual permite operar com:

1. Gemini, quando configurado/disponível;
2. provider OpenAI-compatible;
3. Bastião/local, quando configurado;
4. fallback determinístico offline.

As chamadas possuem timeout e cooldown para evitar que uma falha de provider trave o fluxo.

## Execução local

```powershell
cd dnd_bot
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python bot.py
```

Configure os tokens/providers no `.env`.

SQLite é usado no desenvolvimento. PostgreSQL/Supabase pode ser configurado para produção.

## Testes

```bash
python -m unittest discover -s tests -v
```

O workflow está em `.github/workflows/tests.yml`.

**Importante:** não considerar CI validado apenas porque o workflow existe. É necessário haver uma execução registrada para o commit/PR correspondente.

## Documentação

- [Roadmap](docs/ROADMAP.md)
- [Status e handoff](docs/STATUS.md)
- [Documentação técnica](dnd_bot/README.md)

## Próxima ordem de trabalho

### P0, estabilizar o que já existe

1. Confirmar o novo reconhecimento de movimento no Telegram.
2. Testar tentativa de destino desconhecido sem teleporte.
3. Serializar `/acao` por chat/campanha.
4. Repetir duas ou mais ações rápidas e verificar que nenhuma resposta antiga sobrescreve uma nova.
5. Testar dois jogadores agindo em sequência.
6. Reiniciar o bot e confirmar que aventura, local e progresso continuam.
7. Confirmar CI no GitHub.

### P1, tornar consequências realmente mecânicas

1. Fazer o narrador devolver consequências estruturadas, além de texto.
2. Validar cada consequência contra AdventureState.
3. Aplicar movimento somente quando o destino for permitido.
4. Modelar descobertas, NPCs, pistas e eventos por IDs estruturados.
5. Parar de depender de alterações textuais em `novo_contexto` para representar fatos importantes.

### P2, campanha robusta

1. Separar Campaign, Player e Character.
2. Criar histórico transacional de eventos.
3. Persistir NPCs, locais, quests, itens e fatos como entidades.
4. Implementar ContextBuilder/MemoryStore.
5. Consolidar AI Manager.

## O que ainda não é

O projeto **não é ainda um D&D 5e completo** e não deve ser tratado como produto final.

Ainda faltam, entre outros:

- ficha completa;
- HP/CA/nível/XP completos;
- inventário/equipamentos;
- condições;
- monstros estruturados;
- combate completo;
- death saves;
- regras completas de classe;
- campanha independente do chat;
- memória de longo prazo;
- AI Manager;
- geração dinâmica com múltiplos caminhos;
- pistas redundantes;
- observabilidade e testes de carga;
- painel web e recursos de produto.

## Princípio de segurança do projeto

**A IA pode dizer o que acontece na história, mas não pode ganhar autoridade para quebrar as regras do jogo.**

O objetivo da próxima fase é transformar o protótipo jogável em um motor de campanha que continue consistente mesmo quando dois jogadores agirem ao mesmo tempo, o provider responder tarde ou o jogador tentar fazer algo que o mundo ainda não conhece.
