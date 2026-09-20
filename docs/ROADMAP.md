# Roadmap de desenvolvimento

Este documento representa o estado de engenharia conhecido ao final da rodada de estabilização de setembro de 2026.

## Marco atual

**Marco: núcleo jogável + auditoria de estabilidade em andamento.**

O bot já consegue criar personagens, criar/retomar aventuras, interpretar ações, executar testes, narrar consequências e persistir parte do estado. O próximo trabalho não é adicionar dezenas de funcionalidades: é tornar esse fluxo confiável sob ações consecutivas, concorrência, reinício e entradas imprevisíveis.

---

## P0, estabilidade do fluxo real

### Concluído

- [x] Corrigir criação/retomada de aventura.
- [x] Evitar reset implícito de campanha.
- [x] Persistir personagens por usuário/chat.
- [x] Persistir AdventureState na sessão.
- [x] CAS para atualização de contexto.
- [x] Validar JSON/narrativa retornados pela IA.
- [x] Rejeitar placeholders narrativos genéricos.
- [x] Fallback narrativo determinístico.
- [x] Timeout real de provider.
- [x] Cooldown/fallback entre providers.
- [x] Fallback local/offline.
- [x] Telegram com chunking seguro.
- [x] Geração de imagem fora do event loop.
- [x] Movimento validado pelo grafo de locais.
- [x] Evitar teleporte para destino desconhecido.
- [x] Reconhecer formas informais de movimento.
- [x] Registrar ações no progresso da aventura.
- [x] Preservar contexto em atualização concorrente via CAS.

### Ainda aberto

- [ ] Lock por chat/campanha durante processamento de `/acao`.
- [ ] Garantir que respostas atrasadas de provider não sejam aplicadas sobre estado novo.
- [ ] Testar duas ações rápidas no mesmo chat.
- [ ] Testar dois jogadores agindo em sequência.
- [ ] Testar reinício do processo durante campanha.
- [ ] Confirmar CI verde para o commit final.
- [ ] Consolidar merge da linha de estabilidade para `main`.

**Critério de pronto:** duas ou mais ações simultâneas não podem apagar, repetir ou reverter uma consequência válida de outra ação.

---

## P1, motor determinístico

### Já existe

- [x] Dice engine.
- [x] Modificadores.
- [x] Proficiência básica.
- [x] Ability checks básicos.
- [x] Saving throws básicos.
- [x] Character model inicial.
- [x] GameEngine inicial.
- [x] AdventureState.
- [x] ActionResolver.
- [x] Ações rotineiras sem teste.
- [x] Ações de risco encaminhadas para testes.
- [x] Criação 4d6 drop-lowest.
- [x] Bônus raciais.
- [x] Combate inicial.

### Próximo

- [ ] Consolidar Skill Check completo no GameEngine.
- [ ] Consolidar Saving Throw completo no GameEngine.
- [ ] Event model transacional.
- [ ] Repository transacional.
- [ ] Inventário/equipamentos determinísticos.
- [ ] Condições determinísticas.

---

## P2, personagem completo

- [ ] HP máximo/atual.
- [ ] CA.
- [ ] Nível.
- [ ] XP.
- [ ] Bônus de proficiência por nível.
- [ ] Todas as perícias completas.
- [ ] Salvaguardas e proficiências completas.
- [ ] Armas, armaduras e ferramentas.
- [ ] Inventário.
- [ ] Equipamentos e CA.
- [ ] Condições.
- [ ] Recursos de classe.
- [ ] Evolução de nível.
- [ ] Sub-raças/subclasses conforme escopo.

---

## P3, combate completo

### Já existe no núcleo

- [x] Iniciativa.
- [x] Turnos.
- [x] Movimento em grade.
- [x] Ataques.
- [x] Dano.
- [x] Crítico.
- [x] Dash.
- [x] Dodge.
- [x] Disengage.
- [x] Ação bônus/reação como estrutura inicial.

### Falta

- [ ] Condições.
- [ ] Cobertura.
- [ ] Alcance completo.
- [ ] Death saves.
- [ ] Monstros/inimigos estruturados.
- [ ] Recursos de classe.
- [ ] Ações específicas por classe.
- [ ] Loot/equipamentos.
- [ ] Combate completo com múltiplos inimigos.

---

## P4, campanha persistente

### Já existe

- [x] AdventureState.
- [x] Locais, NPCs, quests, encounters, itens, flags e progresso no estado.
- [x] Persistência inicial de AdventureState.
- [x] SQLite.
- [x] PostgreSQL/Supabase.

### Falta

- [ ] Campaign como entidade independente.
- [ ] Players vinculados a Campaign.
- [ ] Characters persistentes como entidades próprias.
- [ ] NPCs persistentes.
- [ ] Locais/mapas persistentes.
- [ ] Itens persistentes.
- [ ] Histórico transacional de eventos.
- [ ] Consequências persistentes abrangentes.
- [ ] Separação definitiva entre campanha e chat.

---

## P5, narrativa com estado real

Este é o próximo grande salto de qualidade.

Hoje a narrativa já evita placeholders e registra eventos no contexto, mas ainda existe dependência excessiva de texto livre.

### Falta

- [ ] Retorno estruturado de consequências.
- [ ] IDs de entidades em descobertas e interações.
- [ ] Movimento como consequência validada.
- [ ] Descobertas como fatos estruturados.
- [ ] Reações de NPCs por estado.
- [ ] Eventos transacionais.
- [ ] Separação entre narrativa e alteração de estado.

**Meta:** a IA pode narrar uma consequência, mas somente uma consequência validada pode alterar o mundo.

---

## P6, memória e ContextBuilder

- [ ] ContextBuilder.
- [ ] MemoryStore.
- [ ] Resumo automático.
- [ ] Seleção de memória relevante.
- [ ] Memória episódica.
- [ ] Fatos persistentes.
- [ ] Lore do mundo.
- [ ] Proteção contra contradições.

---

## P7, AI Manager

- [ ] Interface única de providers.
- [ ] Structured outputs padronizados.
- [ ] Retry centralizado.
- [ ] ContextBuilder integrado.
- [ ] Tool calling.
- [ ] Consulta de estado por ferramentas.
- [ ] Consulta de regras por ferramentas.
- [ ] Separar responsabilidades do `narrator.py`.

---

## P8, geração dinâmica de aventuras

### Já existe

- [x] Schema inicial.
- [x] Mundo/região/cidade.
- [x] Locais e conexões.
- [x] NPCs.
- [x] Encounters.
- [x] Quests.
- [x] Itens.
- [x] Segredos.
- [x] Validação estrutural.
- [x] Validação semântica.
- [x] Validação de referências.
- [x] Validação de alcançabilidade inicial.

### Falta

- [ ] Validar todas as conexões.
- [ ] Validar todas as referências cruzadas.
- [ ] Validar caminho sequencial das quests.
- [ ] Múltiplos caminhos para objetivos importantes.
- [ ] Pistas redundantes.
- [ ] Pistas como entidades.
- [ ] Evitar linearidade rígida.
- [ ] Dependências narrativas explícitas.
- [ ] Caminhos alternativos realmente independentes.

---

## P9, Diretor de Cena

### Já existe

- [x] Liberdade.
- [x] Oportunidade.
- [x] Sugestão.
- [x] Intervenção.
- [x] Detecção de estagnação.
- [x] Decisão/votação.
- [x] Maioria absoluta.
- [x] Empate sem execução.
- [x] Participação individual.
- [x] Registro de decisão/recusa.

### Falta

- [ ] Botões de votação no Telegram.
- [ ] Janela de votação real.
- [ ] Narração específica dos resultados.
- [ ] Diretor baseado em pistas.
- [ ] Pressão/urgência persistente.
- [ ] Consequências posteriores de recusas.
- [ ] Intervenções mais sofisticadas sem retirar agência.

---

## P10, simulador

### Já existe

- [x] CampaignSimulator.
- [x] PlayerAgent.
- [x] Agentes scripted, goal-driven e personality.
- [x] Exploração.
- [x] Testes.
- [x] Combate inicial.
- [x] Quests.
- [x] Decisões.
- [x] Participação/recusa.
- [x] Diretor.
- [x] Validação durante execução.
- [x] Detecção de loops.
- [x] Relatório.

### Falta

- [ ] Desvios imprevisíveis.
- [ ] Persistência real.
- [ ] Integração com ContextBuilder.
- [ ] Integração com AI Manager.
- [ ] Logs estruturados.
- [ ] Métricas de provider/custo.
- [ ] Métricas de NPCs/pistas.
- [ ] Critérios de falha completos.
- [ ] Vertical slice completo ponta a ponta.

---

## P11, multimídia

- [ ] Retratos de NPCs.
- [ ] Imagens de locais.
- [ ] Mapas.
- [ ] Voz.
- [ ] Sons.
- [ ] Handouts.
- [ ] Gerenciamento de mídia.

---

## P12, produção

- [ ] Logs estruturados.
- [ ] Métricas.
- [ ] Health check.
- [ ] Backup/restore.
- [ ] Rate limiting.
- [ ] Controle de custos.
- [ ] Alertas.
- [ ] Testes de carga.
- [ ] Testes de longa duração.
- [ ] Observabilidade dos providers.

---

## P13, produto

- [ ] Múltiplas campanhas.
- [ ] Mestre humano + IA.
- [ ] Campanhas solo.
- [ ] Painel web.
- [ ] Fichas web.
- [ ] Mapa interativo.
- [ ] Editor de campanha.
- [ ] Biblioteca de NPCs.
- [ ] Exportação PDF.
- [ ] Compartilhamento de campanhas.

---

# Ordem de execução de amanhã

**1. Estabilidade → 2. consequências estruturadas → 3. persistência transacional → 4. personagem/combatente completo → 5. memória/ContextBuilder → 6. AI Manager → 7. geração dinâmica → 8. simulador → 9. produção/produto.**

Não adicionar novas features grandes antes de fechar o P0.

## Critério de qualidade

Só marcar um item como concluído quando:

- existe implementação;
- existe teste quando aplicável;
- não depende de comportamento manual escondido;
- está documentado;
- limitações conhecidas estão registradas.

## Marco técnico

O projeto já deixou de ser apenas um "bot que chama uma IA para contar uma história". Agora existe um núcleo com:

**intenção → regra → teste → estado → narrativa → persistência.**

O trabalho seguinte é fazer esse núcleo resistir ao mundo real: concorrência, reinício, respostas atrasadas, jogadores imprevisíveis e consequências que realmente alteram o mundo.
