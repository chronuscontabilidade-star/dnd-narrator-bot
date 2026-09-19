# 🎲 D&D Narrator Bot

Narrador de RPG D&D com IA (Gemini) para Telegram.

---

## ⚙️ Setup — Passo a Passo

### 1. Criar o bot no Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie `/newbot`
3. Escolha um nome (ex: `Narrador DnD`)
4. Escolha um username terminado em `bot` (ex: `NarradorDnD_bot`)
5. Copie o **token** que o BotFather te enviar

### 2. Pegar a API Key do Gemini

1. Acesse: https://aistudio.google.com/app/apikey
2. Clique em **"Create API key"**
3. Copie a chave gerada

### 3. Configurar o projeto

```bash
# Clone ou copie os arquivos para uma pasta
cd dnd_bot

# Instale as dependências
pip install -r requirements.txt

# Configure as chaves
cp .env.example .env
# Edite o .env com seu editor favorito e coloque os tokens
```

Edite o `.env`:
```
TELEGRAM_TOKEN=1234567890:ABCdefGhIjKlMnOpQrStUvWxYz
GEMINI_API_KEY=AIzaSy...
```

### 4. Rodar o bot

```bash
python bot.py
```

Pronto! O bot está online. ✅

---

## 🎮 Como jogar

### Iniciando uma partida
1. Adicione o bot a um grupo do Telegram (ou converse diretamente)
2. Use `/nova_aventura` para o Gemini gerar um cenário
3. Cada jogador usa `/entrar Nome Classe Raça` para criar seu personagem

### Durante o jogo
- `/acao` + descrição da ação para interagir com a aventura
- `/cena` para gerar uma imagem do momento atual
- `/ficha` para ver sua ficha de personagem
- `/jogadores` para ver quem está na sessão

### Exemplos de uso
```
/entrar Thorin Guerreiro Anão
/entrar Elowen Maga Elfa

/acao Examino as paredes da masmorra em busca de passagens secretas
/acao Ataco o goblin com minha espada longa!
/acao Tento persuadir o guarda a nos deixar passar

/cena
```

---

## 📁 Estrutura do projeto

```
dnd_bot/
├── bot.py          # Bot Telegram + handlers dos comandos
├── narrator.py     # Integração com Gemini (narrativa + imagem)
├── database.py     # SQLite — sessões, personagens, histórico
├── .env            # Suas chaves (não commitar!)
├── .env.example    # Modelo do .env
├── requirements.txt
└── dnd.db          # Criado automaticamente ao rodar
```

---

## 💡 Dicas

- O bot funciona em **grupos** e em **conversa privada**
- Cada grupo/chat tem sua própria sessão independente
- Use `/nova_aventura` para resetar e começar uma história nova
- O contexto da aventura é atualizado a cada ação, mantendo consistência
- A geração de imagem requer que o Imagen 3 esteja disponível na sua conta Gemini

---

## 🚀 Rodando em produção (opcional)

Para manter o bot sempre online, você pode usar:

**Screen (simples):**
```bash
screen -S dndbot
python bot.py
# Ctrl+A+D para desanexar
```

**Systemd (mais robusto):**
```ini
# /etc/systemd/system/dndbot.service
[Unit]
Description=D&D Narrator Bot

[Service]
WorkingDirectory=/caminho/para/dnd_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
