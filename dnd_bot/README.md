# D&D Narrator Bot - documentação técnica

## Objetivo

Implementar um Mestre de RPG para Telegram baseado em **D&D 5e 2014**, usando IA para narrativa e interpretação, mantendo regras e estado crítico sob controle determinístico do código.

## Responsabilidades

- **IA:** interpreta, narra, propõe conteúdo e auxilia decisões narrativas.
- **ActionResolver:** transforma linguagem natural em intenção estruturada.
- **GameEngine:** aplica/valida regras mecânicas.
- **AdventureState:** representa mundo e progresso.
- **Validator:** verifica consistência.
- **Database:** persiste sessão e estado.

A IA não é autoridade final sobre HP, CA, inventário, turnos ou fatos persistentes.

## Fluxo atual de uma ação

```
/acao
  ↓
sessão/personagem
  ↓
ActionResolver
  ↓
ActionIntent
  ↓
teste determinístico, quando necessário
  ↓
narrador IA ou fallback
  ↓
validação da narrativa
  ↓
AdventureState
  ↓
contexto + histórico
  ↓
persistência
  ↓
Telegram
```

## ActionResolver

O resolver já reconhece, entre outros:

- percepção;
- investigação;
- movimento;
- obstáculos;
- furtividade;
- furto;
- ações sociais;
- ataques;
- escalada/salto;
- ações narrativas;
- ações ambíguas.

Movimento explícito tem prioridade sobre investigação. Isso é importante para frases como:

`ir pra cidade mais próxima procurar uma taverna`

A presença de "procurar" não deve transformar uma tentativa de viagem em teste de Investigação.

Destinos desconhecidos não são considerados alcançados automaticamente.

## Narrativa

O narrador foi endurecido para rejeitar respostas que:

- sejam vazias;
- sejam curtas demais;
- repitam placeholders;
- não alterem o contexto;
- repitam a situação anterior sem fato novo.

O fallback offline também produz consequência concreta para ações comuns.

O objetivo é que uma ação sempre tenha algum resultado observável, inclusive quando o teste falha.

## Estado

AdventureState contém:

- aventura;
- mundo;
- locais;
- NPCs;
- encounters;
- quests;
- itens;
- flags;
- segredos;
- progresso;
- narrativa inicial.

O progresso já registra eventos de ação do jogador.

### Limitação importante

Ainda existe dependência de texto livre em `contexto` para parte das consequências. O próximo passo é representar consequências como objetos estruturados e validar cada alteração antes de aplicá-la.

## Multiplayer

Existe persistência por `user_id + chat_id`, lista de jogadores e mecanismos de CAS para atualização de contexto.

A próxima correção deve adicionar serialização por campanha/chat na camada de processamento de `/acao`. CAS protege a gravação, mas não substitui uma fila/lock para impedir que duas ações sejam processadas simultaneamente com o mesmo snapshot lógico.

## Providers

A implementação suporta fallback entre providers configurados e um modo offline determinístico.

Requisições possuem timeout e o provider problemático entra em cooldown.

## Criação de personagem

A criação atual oferece:

- Humano;
- Elfo;
- Anão;
- Halfling;
- Tiefling;
- Meio-Orc;

e:

- Guerreiro;
- Bárbaro;
- Ladino;
- Mago;
- Clérigo;
- Ranger.

Atributos usam 4d6, descartando o menor, com distribuição orientada pela classe e bônus racial.

A ficha completa de 5e ainda não existe.

## Combate

O núcleo atual cobre iniciativa, turnos, movimento, ações, ataques, dano, crítico, Dash, Dodge e Disengage.

Ainda faltam condições completas, monstros, cobertura, alcance completo, morte/death saves, recursos de classe, ações específicas, loot e outras regras.

## Simulador

O CampaignSimulator existe como ferramenta de engenharia para testar o motor sem Telegram.

Ele já cobre exploração, testes, quests, decisões, participação, Diretor e combate inicial, mas ainda possui trechos de vertical slice e não substitui testes de campanha reais.

## Execução

```bash
python -m unittest discover -s tests -v
```

Bot:

```powershell
cd dnd_bot
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python bot.py
```

## Regra de evolução

**Primeiro estabilizar. Depois tornar consequências estruturadas. Depois ampliar o mundo.**

Evitar adicionar novas camadas de produto enquanto o fluxo básico de ação ainda puder perder, repetir ou sobrescrever estado.
