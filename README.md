# D&D Narrator Bot

Bot de RPG para Telegram baseado em **D&D 5e 2014**, com narrativa generativa, regras determinísticas, campanhas estruturadas e fallback offline.

## Estado atual

A branch `fix/stability-audit-2026-09` contém o primeiro núcleo jogável/testável do projeto.

### O que já existe

- criação guiada de personagens;
- geração determinística de atributos com 4d6, descartando o menor;
- bônus raciais das raças atualmente oferecidas;
- ActionResolver para classificar ações;
- testes de atributos e perícias básicos;
- AdventureState estruturado;
- geração estruturada de aventuras;
- validação estrutural e semântica da aventura;
- GameEngine inicial;
- combate determinístico inicial;
- iniciativa, turnos, movimento, ação, ataque, dano, crítico e estados básicos;
- Diretor de Cena com níveis de intervenção;
- decisões multiplayer com votação e maioria absoluta;
- participação individual após a decisão;
- Campaign Simulator determinístico;
- agentes de jogador com perfis diferentes;
- validação do estado durante a simulação;
- relatório final da simulação;
- testes automatizados de regressão;
- CI básico via GitHub Actions;
- deploy configurado no Railway.

## Arquitetura atual

O princípio central é:

```
IA / Narrador
    ↓ propõe, interpreta e narra
Director / Party
    ↓ organiza oportunidades e decisões
ActionResolver
    ↓ transforma intenção em ação mecânica
GameEngine
    ↓ valida e aplica regras
AdventureState
    ↓ representa o estado atual
Validator
    ↓ detecta inconsistências
Persistência
```

**Regra:** a IA não é a autoridade das regras nem grava diretamente alterações arbitrárias no estado da campanha.

## Simulador

O simulador existe para testar o jogo sem precisar jogar manualmente uma campanha inteira.

Executar:

```bash
python -m dnd_bot.game.simulator
```

Ele consegue exercitar:

- exploração;
- ações;
- testes;
- combate inicial;
- quests;
- decisões multiplayer;
- participação individual;
- Diretor de Cena;
- validação estrutural/semântica;
- detecção de loops;
- relatório de execução.

O simulador atual é propositalmente determinístico e ainda possui alguns trechos de vertical slice/hardcoded. Ele é uma ferramenta de engenharia, não o motor final de campanha.

## Testes

```bash
python -m unittest discover -s tests -v
```

O projeto também possui workflow em `.github/workflows/tests.yml`.

> Observação: a existência do workflow não significa que o último commit esteja com uma execução do GitHub Actions registrada. Esse status deve ser verificado no GitHub antes do merge.

## Execução

```powershell
cd dnd_bot
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python bot.py
```

Configure os tokens/providers no `.env`.

Para desenvolvimento, o banco usa SQLite em `DATABASE_PATH`. Em produção, `SUPABASE_DB_URL` pode apontar para PostgreSQL/Supabase.

Para detalhes de providers, banco, variáveis de ambiente e operação, consulte [`dnd_bot/README.md`](dnd_bot/README.md).

## Documentação

- [Roadmap completo](docs/ROADMAP.md)
- [Documentação técnica do bot](dnd_bot/README.md)

## Estado de maturidade

O projeto está em **fase de construção do núcleo do jogo**, não em fase de produto final.

Ainda não estão completos:

- ficha completa de D&D 5e 2014;
- inventário/equipamentos determinísticos completos;
- condições completas;
- combate completo;
- persistência completa de Campaign/Players/Characters/NPCs/etc.;
- memória de longo prazo e ContextBuilder;
- AI Manager completo;
- geração dinâmica com múltiplos caminhos e pistas redundantes validados;
- simulador de campanha completo e imprevisível;
- multimídia;
- observabilidade/produção;
- painel web e recursos de produto.

## Princípio arquitetural

**A IA narra e interpreta. O código decide, valida e aplica. O banco persiste.**

O objetivo é impedir que uma resposta criativa do modelo altere arbitrariamente HP, inventário, regras, turnos ou estado da campanha.
