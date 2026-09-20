# Roadmap de desenvolvimento

Este roadmap representa o estado real do projeto na branch `fix/stability-audit-2026-09`. Itens marcados como concluídos correspondem ao código que já existe no repositório. Itens marcados como parciais ainda possuem limitações conhecidas.

## Princípios de arquitetura

1. **GameEngine é a autoridade das regras.** A IA interpreta, narra e propõe; o código valida e aplica.
2. **AdventureState é a autoridade do estado atual da aventura.**
3. **IA é substituível.**
4. **Liberdade do jogador é preservada.**
5. **Campanhas são geradas dinamicamente.**
6. **Mecânicas críticas precisam ser testáveis sem jogar uma campanha inteira manualmente.**

---

## P0, estabilidade

- [x] Corrigir bugs críticos da auditoria.
- [x] Multiplayer sem apagar personagens.
- [x] Reset explícito de campanha.
- [x] Proteção contra estado concorrente/CAS.
- [x] Validação de respostas da IA.
- [x] Telegram seguro para mensagens longas.
- [x] Gemini/provider cooldown e fallback.
- [x] Geração de imagem fora do event loop.
- [x] PostgreSQL/Supabase dependency.
- [x] CI criado.
- [ ] Confirmar execução verde do GitHub Actions para a branch/PR atual.
- [ ] Revisar e fazer merge da PR de estabilidade.

---

## P1, núcleo determinístico de D&D 5e 2014

### Já implementado

- [x] Dice engine.
- [x] Modificadores de atributos.
- [x] Proficiência básica.
- [x] Ability checks básicos.
- [x] Saving throws básicos.
- [x] Character model inicial.
- [x] GameEngine inicial.
- [x] AdventureState estruturado.
- [x] ActionResolver inicial.
- [x] Ações rotineiras sem teste.
- [x] Ações de risco encaminhadas para testes.
- [x] Criação de atributos usando 4d6, descartando o menor.
- [x] Bônus raciais das raças atualmente oferecidas.
- [x] Combate inicial: iniciativa, turnos, movimento, ação, ataque, dano, crítico e estados básicos.

### Ainda falta

- [ ] Consolidar Skill Check completo com proficiência dentro do GameEngine.
- [ ] Consolidar Saving Throw completo dentro do GameEngine.
- [ ] Event model transacional.
- [ ] Repository transacional.
- [ ] Inventário e equipamentos como estado determinístico.
- [ ] Condições como estado determinístico.

**Critério de pronto:** o modelo não consegue produzir uma alteração inválida apenas inventando JSON.

---

## P2, personagem completo

- [ ] HP máximo e atual.
- [ ] CA.
- [ ] Nível.
- [ ] XP.
- [ ] Bônus de proficiência por nível.
- [ ] Todas as perícias com aplicação completa.
- [ ] Proficiências de testes de resistência.
- [ ] Proficiências de armas, armaduras e ferramentas.
- [ ] Inventário.
- [ ] Equipamentos e cálculo de CA.
- [ ] Condições.
- [ ] Recursos de classe.
- [ ] Evolução de nível.
- [ ] Sub-raças/subclasses conforme escopo.

**Estado atual:** criação de personagem e atributos funcionam, mas a ficha completa ainda não existe.

---

## P3, combate completo

### Núcleo já implementado

- [x] Iniciativa.
- [x] Ordem de turnos.
- [x] Movimento.
- [x] Ação.
- [x] Ação bônus.
- [x] Reação.
- [x] Ataques.
- [x] Dano.
- [x] Crítico.
- [x] Dash.
- [x] Dodge.
- [x] Disengage.
- [x] Movimento em grade.

### Ainda falta

- [ ] Condições completas.
- [ ] Cobertura.
- [ ] Alcance/distância completo.
- [ ] Morte e death saves.
- [ ] Monstros/inimigos estruturados.
- [ ] Recursos de classe.
- [ ] Ataques e ações específicas por classe.
- [ ] Loot/equipamentos.
- [ ] Combate completo contra múltiplos inimigos sem fixtures do vertical slice.

**Estado atual:** combate é um núcleo determinístico inicial, não ainda o combate completo de D&D 5e.

---

## P4, mundo e campanha persistentes

### Já implementado

- [x] Estrutura inicial de AdventureState.
- [x] Locais, NPCs, quests, encounters, itens, flags, segredos e progresso no estado.
- [x] Persistência inicial de AdventureState na sessão.
- [x] Atualização de progresso, locais, encounters e quests pelo GameEngine.
- [x] SQLite para desenvolvimento.
- [x] PostgreSQL/Supabase para produção.

### Ainda falta

- [ ] Campaign como entidade independente.
- [ ] Players vinculados a Campaign.
- [ ] Characters persistentes como entidades próprias.
- [ ] Persistência completa de NPCs.
- [ ] Persistência completa de locais/mapas.
- [ ] Persistência completa de itens/equipamentos.
- [ ] Histórico transacional de eventos.
- [ ] Consequências persistentes abrangentes.
- [ ] Separar definitivamente campanha de chat.

**Critério de pronto:** fechar o Telegram e continuar a mesma campanha dias depois sem depender do estado da conversa.

---

## P5, memória e Context Builder

- [ ] ContextBuilder.
- [ ] MemoryStore.
- [ ] Resumo automático de eventos.
- [ ] Seleção de memória relevante.
- [ ] Compactação do histórico.
- [ ] Memória episódica.
- [ ] Fatos persistentes.
- [ ] Lore do mundo.
- [ ] Proteção contra contradições entre memória e estado determinístico.

**Nota:** AdventureState já separa parte importante do estado da janela de contexto, mas memória de longo prazo ainda não foi implementada.

---

## P6, arquitetura de IA e AI Manager

### Estado atual

- [x] Providers existentes podem ser configurados/fallback conforme implementação atual.
- [x] Validação básica de respostas estruturadas.
- [x] Cooldown/fallback de provider.
- [x] Provider local/OpenAI-compatible pode operar conforme configuração.
- [x] Separação inicial entre narrativa e mecânicas.

### Ainda falta

- [ ] Provider interface consolidada.
- [ ] AI Manager único.
- [ ] Structured outputs padronizados.
- [ ] Retry controlado centralizado.
- [ ] ContextBuilder integrado.
- [ ] Tool calling.
- [ ] Consulta de estado via ferramentas.
- [ ] Consulta de regras via ferramentas.
- [ ] Separação completa do God class `narrator.py`.

Regra final: a IA nunca grava diretamente no Campaign State.

---

## P7, geração dinâmica de aventuras

### Já implementado

- [x] Schema inicial de AdventureState.
- [x] Prompt de geração estruturada.
- [x] Mundo/região/cidade.
- [x] Locais e conexões.
- [x] NPCs.
- [x] Encounters.
- [x] Quests com etapas.
- [x] Itens.
- [x] Segredos.
- [x] Progresso inicial.
- [x] Validação estrutural.
- [x] Validação semântica básica.
- [x] Validação semântica avançada.
- [x] Validação de existência de referências essenciais.
- [x] Validação de alcançabilidade do alvo acionável atual.

### Ainda falta

- [ ] Validação completa das conexões entre locais.
- [ ] Validação completa de referências entre todas as entidades.
- [ ] Validar caminho sequencial de todos os objetivos de uma quest.
- [ ] Garantir objetivos importantes alcançáveis por múltiplos caminhos.
- [ ] Gerar pistas redundantes para objetivos importantes.
- [ ] Modelar pistas como entidades descobríveis.
- [ ] Evitar aventura linear rígida em geração e execução.
- [ ] Registrar dependências narrativas.
- [ ] Validar que caminhos alternativos são realmente independentes.

---

## P8, Diretor de Cena

### Já implementado

- [x] Nível 0: liberdade.
- [x] Nível 1: oportunidade.
- [x] Nível 2: sugestão.
- [x] Nível 3: intervenção.
- [x] Detecção de estagnação.
- [x] Sugestões relacionadas ao local atual.
- [x] Propostas de ação.
- [x] Decision → Vote → Resolution.
- [x] Contagem de votos.
- [x] Maioria absoluta.
- [x] Empate não executa.
- [x] Jogadores sem voto não são considerados voto válido.
- [x] Participação individual após decisão.
- [x] Testes individuais encaminhados com o personagem participante.
- [x] Registro de decisão como evento.
- [x] Recusa individual registrada.
- [x] Consequência cômica planejada como recurso narrativo futuro, sem regra automática de morte.

### Ainda falta

- [ ] Botões de votação no Telegram.
- [ ] Janela de votação real.
- [ ] Narração específica dos resultados individuais.
- [ ] Diretor baseado em pistas descobertas.
- [ ] Pressão/urgência narrativa persistente.
- [ ] Consequências narrativas posteriores baseadas em recusas.
- [ ] Intervenções mais sofisticadas sem retirar agência.

**Regra de ouro:** o Diretor não deve exigir uma solução específica.

---

## P9, simulador de campanha

### Já implementado

- [x] CampaignSimulator.
- [x] PlayerAgent.
- [x] ScriptedPlayerAgent.
- [x] GoalDrivenPlayerAgent.
- [x] PersonalityPlayerAgent.
- [x] Ações artificiais determinísticas.
- [x] Ações orientadas por objetivo.
- [x] Simulação de exploração.
- [x] Simulação de testes.
- [x] Simulação do combate inicial.
- [x] Simulação de quests.
- [x] Simulação de decisões.
- [x] Participação/recusa individual.
- [x] Intervenção do Diretor de Cena.
- [x] Descoberta/visita de locais.
- [x] Validação estrutural durante a simulação.
- [x] Validação semântica durante a simulação.
- [x] Detecção de loops.
- [x] Detecção de ausência de progresso.
- [x] Relatório final.

### Ainda falta

- [ ] Simulação de desvios imprevisíveis dos jogadores.
- [ ] Persistência real durante a simulação.
- [ ] Execução integrada ao ContextBuilder.
- [ ] Execução integrada ao AI Manager.
- [ ] Logs estruturados.
- [ ] Métricas de provider/tokens/custo.
- [ ] Métricas completas de NPCs e pistas.
- [ ] Critérios de falha completos.
- [ ] Substituir fixtures/hardcodes do vertical slice por resolução genérica.
- [ ] Primeiro vertical slice completo: criação → cena → exploração → pista → teste → NPC → combate → loot → quest → novo local → consequência → desfecho.

**Nota importante:** o simulador atual é uma ferramenta de engenharia determinística. Ele já prova partes relevantes do pipeline, mas ainda não é um simulador de campanha completo.

---

## P10, multimídia

- [ ] Retratos de NPCs.
- [ ] Imagens de locais.
- [ ] Mapas.
- [ ] Voz.
- [ ] Sons.
- [ ] Handouts.
- [ ] Gerenciamento de mídia da campanha.

---

## P11, produção

- [ ] Logs estruturados.
- [ ] Métricas.
- [ ] Health check.
- [ ] Backup.
- [ ] Restore.
- [ ] Rate limiting.
- [ ] Controle de custos.
- [ ] Alertas.
- [ ] Testes de carga.
- [ ] Testes de longa duração.
- [ ] Observabilidade dos providers.

---

## P12, visão de produto

- [ ] Múltiplas campanhas.
- [ ] Mestre humano + IA.
- [ ] Campanhas solo.
- [ ] Painel web.
- [ ] Fichas web.
- [ ] Mapa interativo.
- [ ] Editor de campanha.
- [ ] Biblioteca de NPCs.
- [ ] Exportação para PDF.
- [ ] Sistema de compartilhamento de campanhas.

---

# Ordem de execução atual

**Estabilidade → GameEngine → personagem → combate → campanha persistente → memória/ContextBuilder → AI Manager → geração dinâmica → Diretor de Cena → simulador → multimídia → produção → produto.**

## Próximo bloco técnico recomendado

Antes de adicionar mais funcionalidades narrativas, consolidar o núcleo atual:

1. validar CI no GitHub;
2. generalizar objetivos/quest steps;
3. implementar múltiplos caminhos;
4. modelar pistas redundantes;
5. remover hardcodes do vertical slice;
6. ampliar o simulador;
7. só então avançar para memória/ContextBuilder e AI Manager.

## Critério de qualidade

Nenhum recurso deve ser marcado como concluído apenas porque existe um protótipo.

Um item só deve virar `[x]` quando:

- possui implementação no repositório;
- possui teste quando aplicável;
- não depende de comportamento manual escondido;
- está documentado;
- suas limitações conhecidas estão registradas.

## Marco atual

O projeto já saiu da fase de "bot narrador com regras misturadas à IA" e possui um **núcleo determinístico inicial de RPG + estado estruturado + Diretor + decisão multiplayer + simulador**.

O próximo objetivo é transformar esse núcleo em um motor de campanha realmente robusto, capaz de sobreviver a jogadores imprevisíveis sem depender da memória de uma única chamada de IA.
