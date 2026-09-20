# Status de handoff

**Data:** 20/09/2026  
**Branch de trabalho:** `fix/stability-audit-2026-09`

## Onde chegamos

A rodada de hoje foi uma auditoria prática do fluxo do bot no Telegram.

O objetivo era sair do estado em que a IA respondia com placeholders e chegar a um fluxo em que:

**jogador → intenção → teste → consequência → estado → próxima cena**

Isso foi parcialmente alcançado.

## Problemas encontrados e tratados

### 1. Criação da aventura quebrava depois de criar a ficha

O AdventureState guardava o título dentro de `aventura.titulo`, enquanto o fluxo de criação esperava `titulo` no nível raiz.

**Resultado:** personagem era salvo, sessão podia ser criada, mas a introdução falhava.

**Tratamento:** fluxo de introdução ajustado para usar o título correto e preservar a sessão.

---

### 2. Narrador devolvia placeholders

Exemplos antigos:

- "A cena avança a partir dessa decisão."
- "O narrador descreve o que acontece."
- respostas sem consequência concreta.

**Tratamento:**

- validação da resposta narrativa;
- rejeição de placeholders;
- exigência de novo contexto;
- fallback determinístico;
- instrução explícita para produzir consequência observável.

---

### 3. Falhas de teste não produziam história

O dado era rolado corretamente, mas o resultado podia terminar em uma resposta genérica.

**Tratamento:** sucesso e falha agora são enviados ao narrador com obrigação de respeitar o resultado mecânico. O fallback também produz consequência compatível com falha.

---

### 4. Ação composta podia ser classificada pelo verbo errado

Exemplo:

`olhar ao redor, ... vou chamar o sujeito pra briga`

O resolver encontrava "olhar" antes de perceber o desafio.

**Tratamento:** desafios e provocações foram reconhecidos antes das ações narrativas genéricas.

---

### 5. Movimento informal podia virar Investigação

Exemplo:

`ir pra cidade mais próxima procurar uma taverna`

A palavra "procurar" fazia o resolver escolher Investigação.

**Tratamento:** movimento explícito agora reconhece:

- `ir pra`;
- `vou pra`;
- `seguir pra`;
- `voltar pra`;

e outros padrões equivalentes.

**Próximo passo:** confirmar esse comportamento no Telegram após o deploy.

---

### 6. Destino desconhecido poderia virar teleporte narrativo

O jogador pode pedir uma cidade, taverna ou local que não exista no grafo atual.

**Tratamento:** o resolver e o prompt do narrador foram endurecidos para não considerar o destino alcançado só porque o jogador o mencionou.

O mundo precisa primeiro conhecer/validar o caminho.

---

### 7. Provider lento

O timeout existia como configuração, mas a chamada efetiva não era interrompida no limite.

**Tratamento:** requisição agora usa timeout efetivo e cooldown após falha/timeout.

---

## O que foi observado no último teste

A ação:

`/acao olhar ao redor`

já produziu algo próximo do comportamento desejado:

- descreveu a cena;
- revelou um detalhe novo;
- alterou o contexto;
- ofereceu próximos caminhos.

Isso é uma mudança importante em relação ao placeholder anterior.

Por outro lado, o teste seguinte com:

`/acao ir pra cidade mais proxima procurar uma taverna`

foi interpretado como Investigação na execução observada. O código já recebeu a correção para o padrão de movimento, então esse comportamento precisa ser revalidado na próxima sessão.

## Próximo teste obrigatório

Executar exatamente esta sequência:

1. `/acao olhar ao redor`
2. `/acao ir pra cidade mais proxima procurar uma taverna`
3. `/acao voltar pra onde eu estava`
4. pedir um destino claramente inexistente;
5. enviar duas ações rapidamente;
6. usar dois jogadores em sequência;
7. reiniciar o bot;
8. consultar a cena/aventura novamente.

Verificar:

- tipo de ação;
- rolagem;
- narrativa;
- mudança de contexto;
- local atual;
- histórico;
- ausência de teleporte;
- ausência de repetição de resposta antiga;
- persistência após reinício.

## Próxima correção técnica provável

Adicionar um **lock por `chat_id`/campanha** ao processamento de `/acao`.

Motivo: CAS protege a escrita, mas duas ações podem ainda ser processadas simultaneamente a partir de snapshots diferentes.

Fluxo desejado:

```
ação A ──┐
         ├── fila/lock do chat ──→ estado A ──→ persistência
ação B ──┘
```

Depois disso, testar respostas tardias de provider.

## Próximo grande salto

Quando P0 estiver estável, não partir imediatamente para mais funcionalidades.

O próximo desenho recomendado é:

```
IA
 ↓
Narrativa + Consequências estruturadas
 ↓
Validador
 ↓
GameEngine
 ↓
AdventureState
 ↓
Persistência
```

Exemplo conceitual:

```json
{
  "tipo": "movimento",
  "origem": "farol",
  "destino": "estrada_norte"
}
```

A IA pode sugerir esse resultado, mas o código decide se ele é permitido.

## Estado do projeto em uma frase

> **O bot já joga, mas agora precisamos fazê-lo jogar de forma confiável.**

Essa é a linha de trabalho para a próxima sessão.
