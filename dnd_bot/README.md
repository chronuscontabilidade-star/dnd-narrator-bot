# D&D Narrator Bot - documentação técnica

## Objetivo

Implementar um Mestre de RPG para Telegram baseado em **D&D 5e 2014**, usando IA para narrativa e interpretação, mas mantendo regras e estado crítico sob controle determinístico do código.

## Princípio de responsabilidade

- **IA:** interpreta intenção, gera narrativa, propõe conteúdo e auxilia decisões narrativas.
- **ActionResolver:** transforma linguagem natural em uma intenção mecânica estruturada.
- **GameEngine:** aplica e valida mudanças mecânicas.
- **AdventureState:** representa mundo, locais, NPCs, quests, encontros, itens, flags e progresso.
- **Validator:** verifica consistência estrutural e semântica.
- **Database:** persiste sessões e estado de aventura.

A IA não deve ser tratada como autoridade final sobre HP, CA, inventário, turnos, regras ou estado persistente.

## Estrutura atual

```
dnd_bot/
├── bot.py
├── database.py
├── dice.py
├── narrator.py
├── game/
│   ├── action.py
│   ├── adventure.py
│   ├── character.py
│   ├── character_creation.py
│   ├── combat.py
│   ├── dice.py
│   ├── director.py
│   ├── engine.py
│   ├── participation.py
│   ├── party.py
│   ├── rules.py
│   ├── simulator.py
│   └── validator.py
└── requirements.txt
```

## Fluxo de uma ação

```
mensagem do jogador
       ↓
ActionResolver
       ↓
ActionIntent
       ↓
teste/regra determinística
       ↓
GameEngine
       ↓
AdventureState
       ↓
narrador
       ↓
resposta ao jogador
```

O resultado mecânico deve existir independentemente do texto narrativo produzido pela IA.

## AdventureState

O estado estruturado contém, entre outros:

- aventura;
- mundo;
- locais;
- NPCs;
- encontros;
- quests;
- itens;
- flags;
- segredos;
- progresso;
- narrativa inicial.

As quests possuem etapas e podem apontar para recursos existentes por meio de `alvo`, por exemplo:

```json
{
  "tipo": "local",
  "id": "beco"
}
```

O validator verifica referências, existência dos alvos, localização dos recursos e alcançabilidade do próximo objetivo conhecido.

## Criação de personagem

A geração atual segue a base de D&D 5e 2014 para atributos:

1. rolar 4d6;
2. descartar o menor dado;
3. repetir seis vezes;
4. ordenar os resultados;
5. distribuir conforme prioridade da classe;
6. aplicar bônus raciais.

A classe não concede bônus de atributo nesta implementação. Os bônus vêm da raça.

Raças atualmente oferecidas:

- Humano;
- Elfo;
- Anão;
- Halfling;
- Tiefling;
- Meio-Orc.

A implementação ainda não representa a ficha completa de D&D 5e 2014.

## Combate atual

O módulo `game/combat.py` já possui um núcleo determinístico com:

- iniciativa;
- ordem de turnos;
- movimento em grade;
- ação;
- ação bônus;
- reação;
- Dash;
- Dodge;
- Disengage;
- ataques;
- dano;
- crítico natural 20;
- falha natural 1;
- estados básicos por turno.

O combate atual é um **núcleo inicial**, não a implementação completa de combate de D&D 5e.

Ainda faltam, entre outros:

- monstros estruturados;
- condições completas;
- cobertura;
- alcance detalhado;
- morte e death saves;
- recursos de classe;
- ataques múltiplos;
- ações bônus específicas;
- loot/equipamentos;
- regras completas de combate.

## Diretor de Cena

`SceneDirector` possui quatro níveis:

- `none`: liberdade total;
- `opportunity`: oportunidade narrativa;
- `suggestion`: sugestões quando a cena está parada;
- `intervention`: intervenção narrativa para evitar estagnação prolongada.

A regra é **não forçar uma solução única**.

Quando há decisão coletiva:

```
Director
   ↓
PartyDecision
   ↓
votos
   ↓
PartyDecisionResolver
   ↓
opção vencedora
   ↓
PartyParticipationResolver
   ↓
participação individual
   ↓
execução
```

A maioria necessária atualmente é absoluta. Empate ou ausência de maioria não executa a ação.

Uma recusa individual é registrada, mas não gera automaticamente morte ou outra punição no GameEngine. Existe no roadmap a possibilidade de o narrador usar essa recusa em uma consequência narrativa posterior, inclusive de forma cômica.

## Campaign Simulator

O simulador permite testar o núcleo do jogo sem Telegram.

Componentes principais:

- `PlayerAgent`;
- `ScriptedPlayerAgent`;
- `GoalDrivenPlayerAgent`;
- `PersonalityPlayerAgent`;
- `CampaignSimulator`.

Os agentes podem:

- escolher ações;
- votar;
- aceitar/recusar participação;
- explorar;
- interagir com o Diretor;
- seguir objetivos.

O simulador valida o estado durante a execução e produz métricas/relatório.

### Limitações atuais do simulador

O vertical slice ainda possui algumas decisões específicas de teste, incluindo referências de quest e combate em pontos do código. Isso é deliberado para provar o pipeline antes de generalizá-lo.

O próximo estágio deve substituir esses trechos por resolução genérica baseada em objetivos/eventos.

## Validator

O validator já cobre:

- IDs;
- referências entre entidades;
- localização atual;
- conexões;
- locais descobertos/visitados;
- NPCs;
- itens;
- encounters;
- quests;
- etapas;
- alvos estruturados;
- alcançabilidade do objetivo atual;
- consistência básica de quests.

Também existem testes específicos para casos de referência quebrada e objetivos inalcançáveis.

## Persistência

A implementação atual mantém sessões e AdventureState no banco e possui suporte a SQLite para desenvolvimento e PostgreSQL/Supabase para produção.

A persistência completa de entidades de campanha ainda não está concluída.

A arquitetura futura separará:

```
Campaign
 ├── Players
 ├── Characters
 ├── NPCs
 ├── Locations
 ├── Quests
 ├── Encounters
 ├── Items
 ├── Events
 └── World Facts
```

## Providers de IA

O projeto possui suporte/fallback para providers usados pela implementação atual, incluindo Gemini e opções compatíveis com OpenAI/Ollama conforme configuração.

A arquitetura futura consolidará isso em um **AI Manager** com interface única para geração, JSON estruturado, narrativa, resumo e classificação.

## Testes

Executar:

```bash
python -m unittest discover -s tests -v
```

O workflow de CI está em:

```
.github/workflows/tests.yml
```

O CI deve ser considerado validado somente quando houver uma execução registrada e bem-sucedida para o commit/PR correspondente.

## Desenvolvimento

A ordem de evolução está documentada em `docs/ROADMAP.md`.

O foco imediato é consolidar o núcleo determinístico e transformar o simulador em uma ferramenta capaz de encontrar problemas que uma campanha manual longa esconderia.
