"""Bot principal - Telegram D&D Narrator."""

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
CLASSES = {"1": "Guerreiro", "2": "Mago", "3": "Clerigo", "4": "Ladino", "5": "Bardo"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bem-vindo ao D&D Narrator Bot!\n\n"
        "Para comecar, me diga:\n"
        "1. Nome do seu personagem\n"
        "2. Classe (Guerreiro, Mago, Clerigo, Ladino, Bardo)\n"
        "3. Raca (Humano, Elfo, Anao, etc.)\n"
        "4. Detalhes adicionais (opcional)\n\n"
        "Vamos comecar! Qual o nome do seu personagem?"
    )
    return ENTRAR_NOME

async def entrar_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nome'] = update.message.text
    await update.message.reply_text(
        f"Otimo, {update.message.text}!\n\n"
        "Agora escolha sua classe:\n"
        "1. Guerreiro\n2. Mago\n3. Clerigo\n4. Ladino\n5. Bardo\n\n"
        "Digite o numero da classe:"
    )
    return ENTRAR_CLASSE

async def entrar_classe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    classe = CLASSES.get(update.message.text, "Guerreiro")
    context.user_data['classe'] = classe
    await update.message.reply_text(
        f"Excelente {classe}!\n\n"
        "Agora me diga sua raca:\n"
        "(Humano, Elfo, Anao, Orc, Halfling, etc.)"
    )
    return ENTRAR_RACA

async def entrar_raca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['raca'] = update.message.text
    await update.message.reply_text(
        "Perfeito! Agora me conte um pouco mais sobre seu personagem.\n"
        "Pode ser historia, personalidade, objetivos, etc.\n\n"
        "(Digite 'pular' se nao quiser adicionar detalhes)"
    )
    return ENTRAR_DETALHES

async def entrar_detalhes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    detalhes = update.message.text
    if detalhes.lower() == 'pular':
        detalhes = ""
    try:
        db.create_character(
            user_id=update.effective_user.id,
            name=context.user_data.get('nome', 'Desconhecido'),
            class_name=context.user_data.get('classe', 'Guerreiro'),
            race=context.user_data.get('raca', 'Humano'),
            details=detalhes
        )
        await update.message.reply_text(
            f"Personagem criado com sucesso!\n\n"
            f"Nome: {context.user_data.get('nome')}\n"
            f"Classe: {context.user_data.get('classe')}\n"
            f"Raca: {context.user_data.get('raca')}\n\n"
            "Use /mychar para ver seu personagem\n"
            "Use /iniciar_historia para comecar sua aventura"
        )
    except Exception as e:
        log.error(f"Erro ao criar personagem: {e}")
        await update.message.reply_text("Erro ao criar personagem. Tente novamente.")
    return ConversationHandler.END

async def mychar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        char = db.get_character(update.effective_user.id)
        if char:
            await update.message.reply_text(
                f"Seu personagem:\n\n"
                f"Nome: {char['name']}\n"
                f"Classe: {char['class']}\n"
                f"Raca: {char.get('race', 'Nao informada')}\n"
                f"Detalhes: {char.get('details', 'Nenhum')}"
            )
        else:
            await update.message.reply_text("Voce nao tem um personagem. Use /start para criar.")
    except Exception as e:
        log.error(f"Erro ao buscar personagem: {e}")
        await update.message.reply_text("Erro ao buscar personagem.")

async def iniciar_historia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        char = db.get_character(update.effective_user.id)
        if not char:
            await update.message.reply_text("Voce nao tem um personagem. Use /start para criar.")
            return
        await update.message.reply_text("Gerando sua historia...")
        historia = narrator.generate_character_intro(char)
        await update.message.reply_text(
            f"{char['name']}, {char['class']} {char.get('race', '')}\n\n"
            f"{historia}"
        )
    except Exception as e:
        log.error(f"Erro ao gerar historia: {e}")
        await update.message.reply_text("Erro ao gerar historia. Tente novamente.")

async def startcampaign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Para iniciar uma campanha, me diga:\n"
        "1. Nome da campanha\n"
        "2. Descricao breve (opcional)\n\n"
        "Digite o nome da campanha:"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponiveis:\n\n"
        "/start - Criar novo personagem\n"
        "/mychar - Ver seu personagem\n"
        "/iniciar_historia - Gerar introducao da sua historia\n"
        "/startcampaign - Iniciar campanha\n"
        "/help - Esta mensagem"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Erro: {context.error}")
    if update:
        await update.message.reply_text("Desculpe, ocorreu um erro. Tente novamente.")

def main():
    log.info("Iniciando bot...")
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ENTRAR_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, entrar_nome)],
            ENTRAR_CLASSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, entrar_classe)],
            ENTRAR_RACA: [MessageHandler(filters.TEXT & ~filters.COMMAND, entrar_raca)],
            ENTRAR_DETALHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, entrar_detalhes)]
        },
        fallbacks=[]
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('mychar', mychar))
    application.add_handler(CommandHandler('iniciar_historia', iniciar_historia))
    application.add_handler(CommandHandler('startcampaign', startcampaign))
    application.add_handler(CommandHandler('help', help_command))
    application.add_error_handler(error_handler)
    log.info("Bot iniciado com sucesso!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
