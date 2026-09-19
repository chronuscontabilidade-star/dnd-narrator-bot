# Roadmap de desenvolvimento

Este roadmap define a evolução do D&D Narrator como um motor de RPG baseado em D&D 5e 2014, com IA generativa como Mestre/narrador, mas sem permitir que a IA seja a autoridade das regras ou do estado do jogo.

## Princípios de arquitetura

1. **GameEngine é a autoridade das regras.** A IA interpreta, narra e propõe; o código valida e aplica.
2. **Campaign State é a autoridade da campanha.** NPCs, locais, quests, itens, flags, eventos e progresso ficam persistidos.
3. **IA é substituível.** O jogo não pode depender da memória ou do comportamento de um modelo específico.
4. **Llama local é secundário/fallback.** O provider principal poderá ser trocado sem alterar o GameEngine.
5. **Liberdade do jogador é preservada.** O sistema pode criar oportunidades e sugestões, mas não deve forçar uma solução.
6. **Campanhas são geradas dinamicamente.** Não existe uma aventura fixa pré-gravada como fonte da verdade.
7. **Toda mecânica crítica precisa ser testável sem jogar uma campanha inteira manualmente.**

---

## P0, estabilidade

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
- [ ] Revisão e merge da PR de estabilidade.

---

## P1, núcleo determinístico de D&D 5e 2014

Meta: retirar regras críticas das mãos da IA.

- [x] Dice engine.
- [x] Modificadores de atributos.
- [x] Proficiência.
- [x] Ability checks.
- [x] Saving throws básicos.
- [x] Character model inicial.
- [x] GameEngine inicial.
- [x] AdventureState estruturado.
- [x] ActionResolver inicial.
- [x] Ações rotineiras sem teste.
- [x] Ações de risco encaminhadas para testes.
- [x] Criação de atributos usando 4d6, descartando o menor.
- [x] Bônus raciais básicos das raças atualmente oferecidas.
- [x] Combate inicial: iniciativa, turnos, movimento, ação, ataque, dano e estados básicos.
- [ ] Consolidar Skill Check completo com proficiência dentro do GameEngine.
- [ ] Consolidar Saving Throw completo dentro do GameEngine.
- [ ] Event model transacional.
- [ ] Repository transacional.
- [ ] Inventário e equipamentos como estado determinístico.
- [ ] Condições como estado determinístico.

Critério de pronto: o modelo não consegue produzir uma alteração inválida apenas inventando JSON.

---

## P2, personagem completo

Meta: transformar a ficha em uma implementação funcional de D&D 5e 2014.

- [ ] HP máximo e atual.
- [ ] CA.
- [ ] Nível.
- [ ] XP.
- [ ] Bônus de proficiência por nível.
- [ ] Todas as perícias.
- [ ] Proficiências de testes de resistência.
- [ ] Proficiências de armas, armaduras e ferramentas.
- [ ] Inventário.
- [ ] Equipamentos e cálculo de CA.
- [ ] Condições.
- [ ] Recursos de classe.
- [ ] Evolução de nível.
- [ ] Sub-raças/subclasses conforme escopo definido.

Critério de pronto: uma ficha criada pelo bot pode participar de uma aventura sem depender de valores inventados pela IA.

---

## P3, combate completo

Implementar progressivamente:

1. iniciativa;
2. ordem de turnos;
3. movimento;
4. ação;
5. ação bônus;
6. reação;
7. ataques;
8. dano;
9. crítico;
10. condições;
11. cobertura;
12. alcance/distância;
13. morte e death saves;
14. monstros/inimigos;
15. loot.

Critério de pronto: batalha simples contra múltiplos inimigos funciona sem intervenção manual.

---

## P4, mundo e campanha persistentes

Meta: separar definitivamente o estado da campanha da conversa.

Entidades principais:

- Campaign
- Players
- Characters
- Locations
- NPCs
- Quests
- Encounters
- Items
- Events
- World Facts
- Flags
- Secrets
- Progress

- [x] Estrutura inicial de AdventureState.
- [ ] Persistência completa das entidades.
- [ ] Relações entre entidades.
- [ ] Histórico de eventos.
- [ ] Progresso de quests.
- [ ] Descoberta/visita de locais.
- [ ] Estado de NPCs.
- [ ] Estado de itens.
- [ ] Consequências persistentes.

Critério de pronto: fechar o Telegram e continuar a mesma campanha dias depois sem perder o mundo.

---

## P5, memória e Context Builder

Meta: impedir que a campanha dependa da janela de contexto da IA.

Criar camadas de contexto:

- contexto imediato da cena;
- eventos recentes;
- memória episódica;
- fatos persistentes;
- lore do mundo;
- estado mecânico;
- objetivos ativos;
- NPCs relevantes;
- locais relevantes;
- pistas descobertas;
- segredos ainda ocultos.

Criar:

- [ ] ContextBuilder.
- [ ] MemoryStore.
- [ ] resumo automático de eventos.
- [ ] seleção de memória relevante.
- [ ] compactação do histórico.
- [ ] proteção contra contradições entre memória e estado determinístico.

Critério de pronto: uma campanha longa não precisa enviar todo o histórico para a IA para manter continuidade.

---

## P6, arquitetura de IA e AI Manager

Meta: tornar o modelo generativo um componente substituível.

Criar uma interface única:

```
AI Manager
  ├── generate()
  ├── generate_json()
  ├── narrate()
  ├── summarize()
  └── classify()
```

Arquitetura alvo:

```
AI Manager
   ├── Primary Provider
   │     └── Gemini
   │
   ├── Secondary Provider
   │     └── Llama local / Bastião
   │
   └── Deterministic fallback
```

- [ ] Provider interface estável.
- [ ] Gemini como provider principal.
- [ ] Llama/Bastião como provider secundário.
- [ ] Structured outputs.
- [ ] Validação de JSON.
- [ ] Retry controlado.
- [ ] Cooldown/fallback por provider.
- [ ] Context Builder integrado ao AI Manager.
- [ ] Separar narrativa de decisões mecânicas.
- [ ] Tool calling.
- [ ] Consulta de estado via ferramentas.
- [ ] Consulta de regras via ferramentas.

Regra: a IA nunca grava diretamente em Campaign State.

---

## P7, geração dinâmica de aventuras

Meta: cada nova campanha possuir uma aventura nova, coerente e estruturada.

A IA deve gerar:

- mundo;
- região;
- cidade/local inicial;
- locais;
- NPCs;
- encontros potenciais;
- quests;
- itens;
- segredos;
- conexões;
- objetivos;
- narrativa inicial.

- [x] Schema inicial de AdventureState.
- [x] Prompt de geração estruturada.
- [x] Validação estrutural básica da aventura.\n- [x] Validação semântica básica da aventura.\n- [x] Validação semântica avançada da aventura.
- [ ] Validação de conexões entre locais.
- [ ] Validação de referências entre NPCs, quests, itens e locais.
- [ ] Garantir objetivos alcançáveis por múltiplos caminhos.
- [ ] Gerar pistas redundantes para objetivos importantes.
- [ ] Evitar aventura linear rígida.
- [ ] Registrar dependências narrativas.

Critério de pronto: uma nova campanha pode ser criada do zero sem utilizar uma aventura pré-gravada como fonte de verdade.

---

## P8, Diretor de Cena

Meta: manter a aventura avançando sem retirar a liberdade dos jogadores.

O Diretor de Cena observa:

- objetivo narrativo atual;
- progresso das quests;
- pistas disponíveis;
- pistas descobertas;
- atividade dos jogadores;
- tempo/urgência;
- estado dos NPCs;
- locais relevantes;
- consequências pendentes.

Ele pode operar em quatro níveis:

### Nível 0, liberdade total

Os jogadores estão avançando normalmente.

Nenhuma intervenção.

### Nível 1, oportunidade narrativa

O sistema introduz naturalmente algo relevante na cena.

Exemplo:

> O taberneiro parece inquieto e olha repetidamente para a porta.

Não existe uma ordem para o jogador.

### Nível 2, sugestão

Quando a cena está estagnada, o sistema pode apresentar ações possíveis.

Exemplo:

```
👁️ Algo chama a atenção de vocês.

1. Observar o taberneiro
2. Conversar com ele
3. Investigar o salão
4. Ignorar e continuar
```

### Nível 3, intervenção narrativa

Quando existe urgência ou risco de estagnação prolongada, o mundo reage.

Exemplo:

> Um sino toca ao longe. Pela janela, uma coluna de fumaça sobe no horizonte.

O sistema cria pressão, mas não escolhe a ação pelo jogador.

### Votação multiplayer

- [x] Criar propostas de ação.
- [ ] Botões de votação no Telegram.
- [ ] Janela de votação.
- [x] Contagem de votos.
- [x] Empates.
- [x] Jogadores que não votaram.
- [x] Execução da ação vencedora.
- [x] Participação individual após decisão.
- [x] Testes individuais podem ser encaminhados ao GameEngine por personagem.
- [ ] Narração dos resultados individuais.
- [x] Registrar a decisão como evento.
- [x] Pipeline determinístico Decision → Vote → Resolution.
- [x] Maioria absoluta para aprovação; empate ou ausência de maioria não executa a ação.

### Regra de ouro

O Diretor de Cena **não deve exigir uma solução específica**.

Objetivos importantes devem possuir múltiplas pistas, caminhos ou oportunidades de descoberta.

### Future, consequências cômicas para personagens que abandonam o grupo

- [ ] Se um personagem recusar uma ação coletiva e decidir seguir sozinho, permitir que o narrador produza posteriormente uma consequência narrativa cômica e desproporcional.
- [ ] Exemplos possíveis: acidente absurdo, encontro improvável, azar banal ou uma morte ridiculamente contextualizada.
- [ ] A consequência deve ser narrativa, não uma regra automática do GameEngine.
- [ ] Registrar a recusa no histórico para que o narrador possa utilizá-la em uma cena posterior.

Exemplo de tom:

> Fulano decidiu continuar sua jornada sozinho.  
> Alguns minutos depois, engasgou com um amendoim e foi de Vasco.

Critério de pronto: jogadores podem ignorar uma pista ou NPC sem destruir a campanha, enquanto o sistema consegue criar novas oportunidades coerentes.

---

## P9, simulador de campanha

Meta principal do desenvolvimento atual: **permitir testar uma campanha inteira automaticamente sem precisar jogá-la manualmente.**

O simulador deverá executar uma campanha artificialmente:

```
criar campanha
    ↓
criar personagens
    ↓
iniciar cena
    ↓
gerar ação
    ↓
ActionResolver
    ↓
GameEngine
    ↓
evento
    ↓
ContextBuilder
    ↓
IA
    ↓
nova ação
    ↓
...
    ↓
desfecho
```

Criar:

- [ ] CampaignSimulator.
- [ ] PlayerAgent.
- [ ] Ações artificiais determinísticas.
- [ ] Ações artificiais orientadas por objetivo.
- [ ] Simulação de exploração.
- [ ] Simulação de testes.
- [ ] Simulação de combate.
- [ ] Simulação de quests.
- [ ] Simulação de NPCs.
- [ ] Simulação de descoberta de locais.
- [x] Simulação de decisões.
- [ ] Simulação de desvios dos jogadores.
- [ ] Intervenção do Diretor de Cena.
- [ ] Persistência durante a simulação.
- [ ] Execução sem Telegram.
- [ ] Logs estruturados.
- [x] Relatório final.\n- [x] Validação estrutural durante a simulação.

### Métricas do simulador

Registrar pelo menos:

- duração da campanha;
- número de ações;
- número de testes;
- sucessos/falhas;
- combates iniciados/concluídos;
- quests iniciadas/concluídas/abandonadas;
- locais descobertos;
- NPCs encontrados;
- pistas descobertas;
- intervenções do Diretor de Cena;
- sugestões apresentadas;
- votações realizadas;
- loops detectados;
- contradições;
- erros de estado;
- falhas de provider;
- chamadas de IA;
- tokens/custo quando disponível.

### Critérios de falha

O simulador deve acusar:

- estado impossível;
- HP inválido;
- item duplicado indevidamente;
- NPC desaparecendo sem evento;
- quest sem caminho possível;
- local referenciado inexistente;
- referência quebrada;
- contradição entre memória e estado;
- IA retornando estrutura inválida;
- loop narrativo;
- campanha sem progresso;
- campanha encerrando sem condições válidas.

### Primeiro marco do simulador

Uma campanha artificial de teste deve conseguir passar por:

```
Criação
  ↓
Cena inicial
  ↓
Exploração
  ↓
Pista
  ↓
Teste
  ↓
NPC
  ↓
Combate
  ↓
Loot
  ↓
Quest
  ↓
Novo local
  ↓
Consequência
  ↓
Desfecho
```

Sem Telegram e sem intervenção humana.

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

## Ordem de execução atual

**Estabilidade → GameEngine → personagem → combate → campanha persistente → memória/ContextBuilder → AI Manager → geração dinâmica → Diretor de Cena → simulador → multimídia → produção → produto.**

### Marco prioritário de hoje

O objetivo de desenvolvimento é chegar ao **P9, Simulador de Campanha**, mesmo que inicialmente ele seja pequeno e determinístico.

A prioridade é ter uma primeira simulação vertical:

**criação → cena → ação → teste → combate → quest → consequência → desfecho → relatório.**

Depois expandimos o simulador até ele conseguir estressar o sistema com campanhas longas e comportamento imprevisível.
