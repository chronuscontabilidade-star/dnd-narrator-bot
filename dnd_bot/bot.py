"""Telegram bot for the D&D narrator — versão corrigida."""
import asyncio
import logging
import os
import time

from dotenv import load_dotenv
from telegram import BotCommand, ForceReply, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

from database import Database
from dice import ATTR_EMOJI, detectar_atributo, escapa, formatar_resultado_dado, modificador, realizar_teste
from narrator import Narrator

load_dotenv()
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

db = Database(path=os.getenv("DATABASE_PATH", "dnd.db"), db_url=os.getenv("SUPABASE_DB_URL"))
narrator = Narrator(os.getenv("GEMINI_API_KEY"))

CLASSES = {
    "Guerreiro": "FOR ou DES, CON — mestre de armas e armaduras",
    "Bárbaro":   "FOR, CON — combatente resistente e fúria",
    "Ladino":    "DES, INT ou CAR — perícias, furtividade e precisão",
    "Mago":      "INT, DES — conjurador arcano e conhecimento",
    "Clérigo":   "SAB, CON — magia divina, cura e proteção",
    "Ranger":    "DES, SAB, CON — exploração e combate à distância",
}
RACAS = {
    "Humano":   "FOR, DES, CON, INT, SAB e CAR +1 — versátil",
    "Elfo":     "DES +2, INT +1 — ágil e ligado à magia",
    "Anão":     "CON +2, SAB +1 — resistente e determinado",
    "Halfling": "DES +2, CAR +1 — ágil e sortudo",
    "Tiefling": "INT +1, CAR +2 — magia e presença marcante",
    "Meio-Orc": "FOR +2, CON +1 — poderoso e resistente",
}
ATRIBUTOS_PADRAO = {
    "Força": 10, "Destreza": 10, "Constituição": 10,
    "Inteligência": 10, "Sabedoria": 10, "Carisma": 10
}


# ─── Helpers de estado ────────────────────────────────────────────────────────

def estado_key(update):
    return update.effective_chat.id, update.effective_user.id

def estados(ctx):
    return ctx.application.bot_data.setdefault("entradas", {})

def teclado(opcoes):
    return ReplyKeyboardMarkup(
        [[f"{nome} — {resumo}"] for nome, resumo in opcoes.items()],
        one_time_keyboard=True, resize_keyboard=True,
    )

def _escapa_seguro(texto) -> str:
    """escapa() tolerante a None."""
    return escapa(str(texto)) if texto is not None else ""

def formatar_atributos(atributos: dict) -> str:
    emoji = {"Força": "💪", "Destreza": "🏃", "Constituição": "❤️",
              "Inteligência": "🧠", "Sabedoria": "👁️", "Carisma": "✨"}
    linhas = []
    for attr in ["Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"]:
        val = atributos.get(attr, ATRIBUTOS_PADRAO.get(attr, 10))
        mod = modificador(val)
        mod_str = f"+{mod}" if mod >= 0 else str(mod)
        linhas.append(f"{emoji.get(attr,'•')} {attr}: {val} ({mod_str})")
    return "\n".join(linhas)

def formatar_sugestoes(sugestoes: list) -> str:
    RISCO_EMOJI = {"baixo": "🟢", "médio": "🟡", "alto": "🔴"}
    linhas = []
    for s in sugestoes[:3]:
        if isinstance(s, dict):
            r = RISCO_EMOJI.get(s.get("risco", "médio"), "🟡")
            attr = s.get("atributo", "")
            attr_e = ATTR_EMOJI.get(attr, "🎲")
            linhas.append(f"{r} {s.get('acao','')} ({attr_e} {attr}, CD {s.get('cd','?')})")
        else:
            linhas.append(f"• {s}")
    return "\n".join(linhas)


# ─── /start & /ajuda ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚔️ *Bem-vindo ao Narrador D&D!*\n\n"
        "Vamos criar seu personagem antes de começar a história.\n"
        "Quando terminar, use `/iniciar_historia` para começar a aventura.\n"
        "Use `/cancelar` para interromper a criação.", parse_mode="Markdown"
    )
    await iniciar_criacao(update, ctx)

async def cmd_ajuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 *Fluxo da partida:*\n"
        "1\\. `/start` — cria seu personagem\n"
        "2\\. `/iniciar_historia` — finaliza a ficha e começa a aventura\n"
        "3\\. `/acao` \\+ descrição — age na história\n\n"
        "*Também disponíveis:*\n"
        "🎲 `/rolar` \\[Atributo\\] \\[CD\\] — rola dado livremente\n"
        "💡 `/sugerir` — sugestões de ação para seu personagem\n"
        "🖼️ `/cena` — descreve a cena atual\n"
        "📜 `/ficha` — sua ficha de personagem\n"
        "👥 `/jogadores` — lista quem está na sessão\n"
        "❌ `/cancelar` — cancela a criação do personagem",
        parse_mode="MarkdownV2"
    )


# ─── Fluxo de criação de personagem ──────────────────────────────────────────

async def iniciar_criacao(update, ctx):
    estados(ctx)[estado_key(update)] = {"etapa": "nome"}
    await update.message.reply_text(
        "🧙 Qual será o *nome* do personagem?\nResponda com o nome ou use /cancelar.",
        parse_mode="Markdown", reply_markup=ForceReply(selective=True)
    )

async def cmd_entrar(update, ctx):
    estados(ctx).pop(estado_key(update), None)
    await iniciar_criacao(update, ctx)

async def receber_nome(update, ctx):
    nome = update.message.text.strip()
    if not nome or len(nome) > 40:
        await update.message.reply_text("⚠️ Envie um nome entre 1 e 40 caracteres.")
        return
    estados(ctx)[estado_key(update)] = {"etapa": "classe", "personagem": {"nome": nome}}
    await update.message.reply_text(
        "2️⃣ Escolha sua *classe:*\n\n" + "\n".join(f"• *{n}:* {d}" for n, d in CLASSES.items()),
        parse_mode="Markdown", reply_markup=teclado(CLASSES),
    )

async def receber_classe(update, ctx):
    escolha = update.message.text.split(" — ", 1)[0].strip()
    if escolha not in CLASSES:
        await update.message.reply_text("⚠️ Escolha uma das classes exibidas.", reply_markup=teclado(CLASSES))
        return
    estado = estados(ctx).get(estado_key(update))
    if not estado:
        return await cmd_entrar(update, ctx)
    estado["personagem"]["classe"] = escolha
    estado["etapa"] = "raca"
    await update.message.reply_text(
        "3️⃣ Escolha sua *raça:*\n\n" + "\n".join(f"• *{n}:* {d}" for n, d in RACAS.items()),
        parse_mode="Markdown", reply_markup=teclado(RACAS),
    )

async def receber_raca(update, ctx):
    escolha = update.message.text.split(" — ", 1)[0].strip()
    if escolha not in RACAS:
        await update.message.reply_text("⚠️ Escolha uma das raças exibidas.", reply_markup=teclado(RACAS))
        return
    estado = estados(ctx).get(estado_key(update))
    if not estado:
        await update.message.reply_text("⚠️ A criação expirou. Use /start novamente.")
        return
    estado["personagem"]["raca"] = escolha
    estado["etapa"] = "detalhes"
    await update.message.reply_text(
        "4️⃣ Descreva detalhes opcionais: arquétipo, manias, medos, objetivo ou histórico.\n"
        "Escreva `nenhum` se prefere que o narrador decida.",
        parse_mode="Markdown", reply_markup=ForceReply(selective=True)
    )

async def receber_detalhes(update, ctx):
    estado = estados(ctx).get(estado_key(update))
    if not estado or "personagem" not in estado:
        await update.message.reply_text("⚠️ A criação expirou. Use /start novamente.")
        return
    detalhes = update.message.text.strip()
    estado["personagem"]["detalhes"] = (
        "" if detalhes.lower() in {"nenhum", "nenhuma", "n/a", "nao", "não"} else detalhes
    )
    estado["etapa"] = "aguardando_inicio"
    await update.message.reply_text(
        "✅ Dados do personagem recebidos!\n\n"
        "Quando estiver pronto, use `/iniciar_historia`.\n"
        "Use /cancelar para descartar a criação.",
        reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown"
    )

async def processar_entrada(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    etapa = estados(ctx).get(estado_key(update), {}).get("etapa")
    if etapa == "nome":      await receber_nome(update, ctx)
    elif etapa == "classe":  await receber_classe(update, ctx)
    elif etapa == "raca":    await receber_raca(update, ctx)
    elif etapa == "detalhes": await receber_detalhes(update, ctx)
    elif etapa == "aguardando_inicio":
        await update.message.reply_text(
            "Use `/iniciar_historia` para finalizar a ficha e começar.", parse_mode="Markdown"
        )

async def cancelar_entrada(update, ctx):
    estados(ctx).pop(estado_key(update), None)
    await update.message.reply_text("❌ Criação cancelada.", reply_markup=ReplyKeyboardRemove())


# ─── /iniciar_historia ────────────────────────────────────────────────────────

async def cmd_iniciar_historia(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chave = estado_key(update)
    estado = estados(ctx).get(chave)
    if not estado or estado.get("etapa") != "aguardando_inicio":
        await update.message.reply_text("⚠️ Termine a criação do personagem primeiro usando /start.")
        return
    p = estado["personagem"]
    await update.message.reply_text("🧙 Finalizando sua ficha e preparando a história...")
    try:
        ficha = await narrator.criar_personagem(p["nome"], p["classe"], p["raca"], p.get("detalhes", ""))
        # CORREÇÃO: garante que todos os 6 atributos existem — evita KeyError no dice.py
        atributos = {**ATRIBUTOS_PADRAO, **ficha.get("atributos", {})}
        if not ficha.get("historia"):
            raise ValueError("ficha incompleta")
        intro = await narrator.iniciar_aventura(update.effective_chat.id)
        db.criar_sessao(update.effective_chat.id, intro["contexto"])
        db.salvar_personagem(
            update.effective_user.id, update.effective_chat.id,
            p["nome"], p["classe"], p["raca"], atributos, ficha["historia"]
        )
    except Exception:
        log.exception("Falha ao iniciar história")
        await update.message.reply_text(
            "⚠️ Não consegui iniciar a história agora. Seus dados continuam preservados; "
            "tente /iniciar_historia novamente."
        )
        return
    estados(ctx).pop(chave, None)
    await update.message.reply_text(
        f"✅ *{_escapa_seguro(p['nome'])} entrou na aventura\\!*\n\n"
        f"📊 *Atributos:*\n{escapa(formatar_atributos(atributos))}\n\n"
        f"📖 *História:* _{_escapa_seguro(ficha['historia'])}_\n\n"
        f"📚 *{_escapa_seguro(intro['titulo'])}*\n\n{_escapa_seguro(intro['narrativa'])}",
        parse_mode="MarkdownV2"
    )

async def cmd_nova_aventura(update, ctx):
    await update.message.reply_text(
        "Para iniciar uma nova partida, use /start e crie um novo personagem."
    )


# ─── /acao — CORRIGIDO: dados conectados ao fluxo ────────────────────────────

async def cmd_acao(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    sessao  = db.obter_sessao(chat_id)
    p       = db.obter_personagem(user_id, chat_id)

    if not sessao or not p:
        await update.message.reply_text("❌ Inicie a história com /start e /iniciar_historia.")
        return

    acao = " ".join(ctx.args).strip() if ctx.args else ""
    if not acao:
        await update.message.reply_text(
            "Use `/acao` seguido da descrição\\.\n"
            "Ex: `/acao Tento roubar o cálice sem ninguém ver`",
            parse_mode="MarkdownV2"
        )
        return

    jogadores = db.listar_jogadores(chat_id)

    # Passo 1 — Gemini avalia se precisa de teste e qual CD
    msg = await update.message.reply_text("🧠 O Mestre avalia sua ação...")
    avaliacao = await narrator.avaliar_acao(sessao, acao)

    # Passo 2 — Rola o dado se necessário e exibe visualmente
    teste = None
    if avaliacao.get("precisa_teste"):
        atributo = detectar_atributo(acao) or avaliacao.get("atributo", "Destreza")
        # Garante que atributo existe na ficha (fallback seguro)
        if atributo not in p["atributos"]:
            atributo = "Destreza"
        cd = int(avaliacao.get("cd", 12))
        teste = realizar_teste(p["atributos"], atributo, dificuldade=cd)
        try:
            await ctx.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text=formatar_resultado_dado(teste, p["nome"]),
                parse_mode="MarkdownV2"
            )
        except Exception:
            await update.message.reply_text(
                formatar_resultado_dado(teste, p["nome"]), parse_mode="MarkdownV2"
            )
        await asyncio.sleep(1.5)  # pausa dramática
        await update.message.reply_text("📖 O narrador descreve o que acontece...")
    else:
        try:
            await ctx.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text="📖 Ação simples — o narrador descreve..."
            )
        except Exception:
            pass

    # Passo 3 — Gemini narra com o resultado real do dado
    resultado = await narrator.narrar_acao_com_dado(sessao, p, jogadores, acao, teste)
    novo_ctx = resultado.get("novo_contexto") or sessao["contexto"]
    db.atualizar_contexto(chat_id, novo_ctx)
    db.registrar_acao(user_id, chat_id, acao, resultado["narrativa"])

    sugestoes_txt = formatar_sugestoes(resultado.get("sugestoes", []))
    texto = f"📖 {resultado['narrativa']}"
    if sugestoes_txt:
        texto += f"\n\n💡 *O que fazer agora?*\n{sugestoes_txt}"
    await update.message.reply_text(texto, parse_mode="Markdown")


# ─── /rolar ───────────────────────────────────────────────────────────────────

async def cmd_rolar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /rolar              → d20 puro
    /rolar Destreza     → d20 + mod de Destreza
    /rolar Força 15     → d20 + mod de Força vs CD 15
    """
    import random
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    p = db.obter_personagem(user_id, chat_id)
    args = ctx.args or []

    # Sem personagem ou sem argumento: d20 puro
    if not p or not args:
        resultado = random.randint(1, 20)
        emoji = "🌟" if resultado == 20 else ("💀" if resultado == 1 else "🎲")
        nome = _escapa_seguro(p["nome"]) if p else "Sem personagem"
        await update.message.reply_text(
            f"🎲 *{nome} rola d20*\n\n{emoji} Resultado: *{resultado}*",
            parse_mode="Markdown"
        )
        return

    # Detecta atributo
    arg0 = args[0].capitalize()
    atributo = None
    for a in p["atributos"]:
        if a.lower().startswith(arg0.lower()):
            atributo = a
            break

    if not atributo:
        lista = ", ".join(p["atributos"].keys())
        await update.message.reply_text(f"⚠️ Atributo não reconhecido. Use um de: {lista}")
        return

    cd = 10
    if len(args) >= 2:
        try:
            cd = int(args[1])
        except ValueError:
            pass

    teste = realizar_teste(p["atributos"], atributo, dificuldade=cd)
    await update.message.reply_text(
        formatar_resultado_dado(teste, p["nome"]), parse_mode="MarkdownV2"
    )


# ─── /sugerir ─────────────────────────────────────────────────────────────────

async def cmd_sugerir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sessao  = db.obter_sessao(chat_id)
    p       = db.obter_personagem(update.effective_user.id, chat_id)

    if not sessao:
        await update.message.reply_text("❌ Nenhuma aventura ativa! Use /start.")
        return
    if not p:
        await update.message.reply_text("❌ Você não tem personagem. Use /start.")
        return

    await update.message.reply_text("💡 O Mestre pensa em opções para você...")
    dados = await narrator.sugerir_acoes(sessao, p)
    sugestoes = dados.get("sugestoes", [])

    if not sugestoes:
        await update.message.reply_text("💡 Nenhuma sugestão disponível no momento.")
        return

    RISCO_EMOJI = {"baixo": "🟢", "médio": "🟡", "alto": "🔴"}
    linhas = []
    for i, s in enumerate(sugestoes[:5], 1):
        if isinstance(s, dict):
            attr   = s.get("atributo", "")
            attr_e = ATTR_EMOJI.get(attr, "🎲")
            risco  = s.get("risco", "médio")
            r_e    = RISCO_EMOJI.get(risco, "🟡")
            linhas.append(
                f"{i}. {r_e} {s.get('acao', '')}\n"
                f"   {attr_e} {attr} | CD {s.get('cd', '?')} | Risco: {risco}"
            )
        else:
            linhas.append(f"{i}. {s}")

    await update.message.reply_text(
        f"💡 *Sugestões para {p['nome']}:*\n\n" + "\n\n".join(linhas) +
        "\n\nUse `/acao` + descrição para agir!",
        parse_mode="Markdown"
    )


# ─── /cena ────────────────────────────────────────────────────────────────────

async def cmd_cena(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sessao  = db.obter_sessao(chat_id)

    if not sessao:
        await update.message.reply_text("❌ Nenhuma aventura ativa! Use /start.")
        return

    await update.message.reply_text("🖼️ Descrevendo a cena atual...")
    # CORREÇÃO: tenta gerar imagem real primeiro, cai pra descrição textual
    resultado = await narrator.gerar_cena(sessao)
    imagem    = await narrator.gerar_imagem(sessao)

    if imagem.get("imagem_bytes"):
        await update.message.reply_photo(
            photo=imagem["imagem_bytes"],
            caption=f"🏰 {resultado.get('descricao', '')}",
        )
    else:
        await update.message.reply_text(f"🏰 *Cena atual:*\n\n{resultado.get('descricao', '')}", parse_mode="Markdown")


# ─── /ficha ───────────────────────────────────────────────────────────────────

async def cmd_ficha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    p = db.obter_personagem(update.effective_user.id, update.effective_chat.id)
    if not p:
        await update.message.reply_text("❌ Você ainda não tem personagem. Use /start.")
        return
    await update.message.reply_text(
        f"📜 *{p['nome']}* — {p['classe']} {p['raca']}\n\n"
        f"{formatar_atributos(p['atributos'])}\n\n"
        f"📖 {p['historia']}",
        parse_mode="Markdown"
    )


# ─── /jogadores ───────────────────────────────────────────────────────────────

async def cmd_jogadores(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    jogadores = db.listar_jogadores(update.effective_chat.id)
    if not jogadores:
        await update.message.reply_text("👥 Nenhum jogador ainda.")
        return
    lista = "\n".join(f"• *{j['nome']}* — {j['classe']} {j['raca']}" for j in jogadores)
    await update.message.reply_text(f"👥 *Jogadores ({len(jogadores)}):*\n\n{lista}", parse_mode="Markdown")


# ─── Setup de comandos ────────────────────────────────────────────────────────

async def configurar_comandos(app):
    await app.bot.set_my_commands([
        BotCommand("start",           "Criar personagem"),
        BotCommand("iniciar_historia","Finalizar ficha e iniciar história"),
        BotCommand("acao",            "Fazer uma ação na aventura"),
        BotCommand("rolar",           "Rolar dado livremente"),
        BotCommand("sugerir",         "Sugestões de ação para seu personagem"),
        BotCommand("cena",            "Descrever a cena atual"),
        BotCommand("ficha",           "Ver sua ficha de personagem"),
        BotCommand("jogadores",       "Listar jogadores na sessão"),
        BotCommand("ajuda",           "Mostrar todos os comandos"),
        BotCommand("entrar",          "Recriar personagem"),
        BotCommand("cancelar",        "Cancelar criação de personagem"),
    ])


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN não encontrado no .env!")

    proxy = os.getenv("TELEGRAM_PROXY") or None
    req_kwargs = dict(connect_timeout=30, read_timeout=60, write_timeout=30, pool_timeout=30, proxy=proxy)
    request         = HTTPXRequest(connection_pool_size=8, **req_kwargs)
    updates_request = HTTPXRequest(connection_pool_size=2, **req_kwargs)

    def build_app():
        app = (
            ApplicationBuilder()
            .token(token)
            .request(request)
            .get_updates_request(updates_request)
            .post_init(configurar_comandos)
            .build()
        )
        # Handlers de comando
        cmds = [
            ("start",            cmd_start),
            ("ajuda",            cmd_ajuda),
            ("entrar",           cmd_entrar),
            ("iniciar_historia", cmd_iniciar_historia),
            ("cancelar",         cancelar_entrada),
            ("nova_aventura",    cmd_nova_aventura),
            ("acao",             cmd_acao),
            ("rolar",            cmd_rolar),      # RESTAURADO
            ("sugerir",          cmd_sugerir),    # RESTAURADO
            ("cena",             cmd_cena),       # RESTAURADO
            ("ficha",            cmd_ficha),
            ("jogadores",        cmd_jogadores),
        ]
        for command, handler in cmds:
            app.add_handler(CommandHandler(command, handler))
        # Handler de texto livre (fluxo de criação de personagem)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_entrada))
        return app

    while True:
        try:
            build_app().run_polling(timeout=30, bootstrap_retries=-1, close_loop=False)
            break
        except (NetworkError, TimedOut) as exc:
            log.error("Falha de rede: %s; tentando novamente em 15 segundos", exc)
            time.sleep(15)


if __name__ == "__main__":
    main()
