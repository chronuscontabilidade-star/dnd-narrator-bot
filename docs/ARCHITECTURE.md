# Arquitetura

## Objetivo

Evoluir o bot de um narrador com persistência para um Mestre de D&D persistente, separando narrativa, regras e estado.

## Arquitetura alvo

Telegram -> Bot Gateway -> Game Orchestrator

O Orchestrator conversa com três componentes principais:

1. GameEngine, responsável por regras e estado determinístico.
2. Event System, responsável por registrar acontecimentos.
3. AI Dungeon Master, responsável por interpretar intenções e narrar consequências.

O GameEngine persiste em SQLite/PostgreSQL através de uma camada de repository.

## Regra de ouro

A IA não é a fonte de verdade do jogo.

Fluxo esperado:

1. Jogador descreve uma ação.
2. IA interpreta a intenção.
3. GameEngine valida se a ação é possível.
4. GameEngine aplica regras, rolagens e alterações.
5. O evento é persistido.
6. A IA recebe o resultado.
7. A IA narra a consequência.

A IA pode propor. O motor valida.

## Estado

Separar quatro tipos de informação:

- Estado atual: HP, CA, posição, inventário e condições.
- Fatos do mundo: NPCs, locais, relações e quests.
- Eventos: ações ocorridas em ordem.
- Memória narrativa: fatos relevantes para continuidade.

## Refatoração planejada

Criar progressivamente os módulos:

- game/engine.py
- game/character.py
- game/combat.py
- game/dice.py
- game/rules.py
- game/inventory.py
- game/quests.py
- game/conditions.py
- game/events.py
- ai/provider.py
- ai/manager.py
- ai/gemini.py
- ai/bastiao.py
- ai/openai_compatible.py
- dm/narrator.py
- dm/planner.py
- dm/memory.py
- dm/prompts.py
- storage/repository.py

Não fazer rewrite big-bang. Cada extração deve manter a suíte de testes passando.
