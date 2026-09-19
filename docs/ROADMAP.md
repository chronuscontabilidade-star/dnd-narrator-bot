# Roadmap de desenvolvimento

## P0, estabilização

Meta: rodar uma sessão sem os bugs críticos conhecidos.

- [x] Multiplayer sem apagar personagens.
- [x] Reset explícito de campanha.
- [x] Proteção contra estado concorrente.
- [x] Validação de respostas da IA.
- [x] Telegram seguro para mensagens longas.
- [x] Gemini e geração de imagem atualizados.
- [x] PostgreSQL/Supabase dependency.
- [x] CI criado.
- [ ] CI verde.
- [ ] Revisão e merge.

## P1, GameEngine

Meta: retirar regras críticas das mãos da IA.

Entregáveis: GameState, GameEngine, Character, Dice, Rules, Event e repository transacional.

Fluxo: ação -> interpretação -> validação -> aplicação -> evento -> narrativa.

Critério de pronto: o modelo não consegue produzir uma alteração inválida apenas inventando JSON.

## P2, personagem completo

- [ ] HP máximo e atual.
- [ ] CA.
- [ ] Nível e XP.
- [ ] Proficiências e perícias.
- [ ] Inventário e equipamentos.
- [ ] Condições.
- [ ] Recursos de classe.

## P3, combate

Implementar em ordem: iniciativa, turnos, movimento, ação, ação bônus, reação, ataque, dano, condições, morte/death saves e monstros.

Critério de pronto: batalha simples contra múltiplos inimigos funciona sem intervenção manual.

## P4, campanhas persistentes

Separar Campaign, Players, Characters, Locations, NPCs, Quests, Events e World Facts.

Critério de pronto: fechar o Telegram e continuar a mesma campanha dias depois.

## P5, memória

Criar contexto imediato, memória episódica, fatos persistentes e lore/documentos.

Critério de pronto: NPCs lembram acontecimentos importantes sem enviar todo o histórico para a IA.

## P6, IA como Mestre

- [ ] Tool calling.
- [ ] Consulta de estado.
- [ ] Consulta de regras.
- [ ] Planejamento de cena.
- [ ] NPC planner.
- [ ] Consequências.
- [ ] Memória seletiva.
- [ ] Roteamento entre providers.

## P7, Bastião

Integrar o Bastião como provider/cérebro local através do Provider Manager. O Bastião consulta e modifica o jogo somente através das ferramentas do GameEngine.

## P8, multimídia

Imagens, retratos, mapas, voz, sons e handouts.

## P9, produção

Logs estruturados, métricas, health check, backup, restore, rate limiting, controle de custos, alertas e testes de carga.

## P10, visão de produto

Múltiplas campanhas, mestre humano + IA, campanhas solo, painel web, fichas web, mapa interativo, editor de campanha, biblioteca de NPCs e exportação para PDF.

## Ordem de execução

**Estabilidade -> GameEngine -> personagens -> combate -> mundo persistente -> memória -> IA/tool calling -> Bastião -> multimídia -> produção.**
