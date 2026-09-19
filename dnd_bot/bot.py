"""
Bot principal - Telegram D&D Narrator.
CÓ³digo limpo e simplificado, sem proxy.
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

from database import Database
from narrator import Narrator

db = Database(path=os.getenv("DATABASE_PATH", "dnd.db"), db_url=os.getenv("SUPABASE_DB_URL"))
narrator = Narrator(os.getenv("GEMINI_API_KEY"))

ENTRAR_NOME, ENTRAR_CLASSE, ENTRAR_RACA, ENTRAR_DETALHES = range(4)
CLASSES = {"1": "Guerreiro", "2": "Mago", "3": "Clé©©rigo", "4": "Ladino", "5": "Bardo"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bem-vindo ao D&D Narrator Bot!

Para começ​ar, me diga:
1. Nome do seu personagem
2. Classe (Guerreiro, Mago, Clé©©rigo, Ladino, Bardo)
3. Raç©©a (Humano, Elfo, Anã©£o, etc.)
4. Detalhes adicionais (opcional)

Vamos começ​ar! Qual o nome do seu personagem?")
    return ENTRAR_NOME

async def entrar_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nome'] = update.message.text
    await update.message.reply_text(f"Ó³timo, {update.message.text}!

Agora escolha sua classe:
1. Guerreiro
2. Mago
3. Clé©©rigo
4. Ladino
5. Bardo

Digite o nú​mero da classe:")
    return ENTRAR_CLASSE

async def entrar_classe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    classe = CLASSES.get(update.message.text, "Guerreiro")
    context.user_data['classe'] = classe
    await update.message.reply_text(f"Excelente {classe}!

Agora me diga sua raç©©a:
(Humano, Elfo, Anã©£o, Orc, Halfling, etc.)")
    return ENTRAR_RACA

async def entrar_raca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['raca'] = update.message.text
    await update.message.reply_text("Perfeito! Agora me conte um pouco mais sobre seu personagem.
Pode ser histó​ria, personalidade, objetivos, etc.

(Digite 'pular' se nã©£o quiser adicionar detalhes)")
    return ENTRAR_DETALHES

async def entrar_detalhes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    detalhes = update.message.text
    if detalhes.lower() == 'pular':
        detalhes = ""
    try:
        db.create_character(user_id=update.effective_user.id, name=context.user_data.get('nome', 'Desconhecido'), class_name=context.user_data.get('classe', 'Guerreiro'), race=context.user_data.get('raca', 'Humano'), details=detalhes)
        await update.message.reply_text(f"Personagem criado com sucesso!

Nome: {context.user_data.get('nome')}
Classe: {context.user_data.get('classe')}
Raç©©a: {context.user_data.get('raca')}

Use /mychar para ver seu personagem
Use /startcampaign para iniciar uma campanha")
    except Exception as e:
        log.error(f"Erro ao criar personagem: {e}")
        await update.message.reply_text("Erro ao criar personagem. Tente novamente.)")
    return ConversationHandler.END

async def mychar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        char = db.get_character(update.effective_user.id)
        if char:
            await update.message.reply_text(f"Seu personagem:

Nome: {char['name']}
Classe: {char['class']}
Raç©©a: {char.get('race', 'Nã©£o informada')}
Detalhes: {char.get('details', 'Nenhum')}")
        else:
            await update.message.reply_text("VocÅª nã©£o tem um personagem. Use /start para criar.")
    except Exception as e:
        log.error(f"Erro ao buscar personagem: {e}")
        await update.message.reply_text("Erro ao buscar personagem.")

async def startcampaign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Para iniciar uma campanha, me diga:
1. Nome da campanha
2. Descriç©£o breve (opcional)

Digite o nome da campanha:")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Comandos disponí©©veis:

/start - Criar novo personagem
/mychar - Ver seu personagem
/startcampaign - Iniciar campanha
/help - Esta mensagem")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Erro: {context.error}")
    if update:
        await update.message.reply_text("Desculpe, ocorreu um erro. Tente novamente.")

def main():
    log.info("Iniciando bot...")
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    conv_handler = ConversationHandler(entry_points=[CommandHandler('start', start)], states={ENTRAR_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, entrar_nome)], ENTRAR_CLASSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, entrar_classe)], ENTRAR_RACA: [MessageHandler(filters.TEXT & ~filters.COMMAND, entrar_raca)], ENTRAR_DETALHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, entrar_detalhes)]}, fallbacks=[])
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('mychar', mychar))
    application.add_handler(CommandHandler('startcampaign', startcampaign))
    application.add_handler(CommandHandler('help', help_command))
    application.add_error_handler(error_handler)
    log.info("Bot iniciado com sucesso!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()