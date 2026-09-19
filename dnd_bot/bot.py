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

RACAS = {
    "Humano": {"vantagens": "Versátil e equilibrado.", "desvantagens": "Menos especializado que outras raças."},
    "Elfo": {"vantagens": "Agilidade e afinidade com magia.", "desvantagens": "Menor resistência física."},
    "Anão": {"vantagens": "Resistência e força de vontade.", "desvantagens": "Menor mobilidade."},
    "Halfling": {"vantagens": "Agilidade, sorte e carisma.", "desvantagens": "Menor porte e força bruta."},
    "Tiefling": {"vantagens": "Presença marcante e afinidade mágica.", "desvantagens": "Pode enfrentar preconceito no cenário."},
    "Meio-Orc": {"vantagens": "Força e resistência excepcionais.", "desvantagens": "Menos adequado a conceitos sutis."},
}
CLASSES = {
    "Guerreiro": {"vantagens": "Versátil no combate e resistente.", "desvantagens": "Poucas ferramentas mágicas."},
    "Bárbaro": {"vantagens": "Alta resistência e dano físico.", "desvantagens": "Menos opções fora do combate."},
    "Ladino": {"vantagens": "Furtividade, perícias e precisão.", "desvantagens": "Menos resistente em confronto direto."},
    "Mago": {"vantagens": "Grande variedade de magia.", "desvantagens": "Frágil fisicamente e dependente de recursos."},
    "Clérigo": {"vantagens": "Cura, proteção e magia divina.", "desvantagens": "Precisa administrar recursos e responsabilidades do grupo."},
    "Ranger": {"vantagens": "Exploração, rastreamento e combate à distância.", "desvantagens": "Mais especializado em certos ambientes e estilos."},
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

def teclado_nomes(opcoes):
    return ReplyKeyboardMarkup(
        [[nome] for nome in opcoes],
        one_time_keyboard=True, resize_keyboard=True,
    )

def formatar_opcoes(opcoes: dict, titulo: str) -> str:
    linhas = [titulo, ""]
    for nome, dados in opcoes.items():
        linhas.append(
            f"🎭 {nome}\n"
            f"   ✅ Vantagens: {dados['vantagens']}\n"
            f"   ⚠️ Desvantagens/considerações: {dados['desvantagens']}"
        )
    return "\n\n".join(linhas)

def _escapa_seguro(texto) -> str:
    """escapa() tolerante a None."""
    return escapa(str(texto)) if texto is not None else ""

def formatar_ficha_completa(p: dict) -> str:
    return (
        "📜 FICHA COMPLETA\n\n"
        f"👤 Nome: {p.get('nome', '')}\n"
        f"🧬 Raça: {p.get('raca', '')}\n"
        f"⚔️ Classe: {p.get('classe', '')}\n\n"
        f"💪 ATRIBUTOS\n{formatar_atributos(p.get('atributos', {}))}\n\n"
        f"🎭 CONCEITO / ARQUÉTIPO\n{p.get('detalhes') or 'Não informado'}\n\n"
        f"📖 HISTÓRIA\n{p.get('historia', '')}"
    )

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


async def enviar_texto_seguro(update, texto: str, **kwargs):
    """Envia texto sem depender de Markdown e respeitando o limite do Telegram."""
    limite = 4000
    texto = str(texto or "")
    if not texto:
        return
    for inicio in range(0, len(texto), limite):
        await update.message.reply_text(texto[inicio:inicio + limite], **kwargs)


# ─── /start & /ajuda ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚔️ *Bem-vindo ao Narrador D&D!*\n\n"
        "Vamos criar seu personagem antes de começar a história.\n"
        "Ao terminar os detalhes, a ficha será gerada e a aventura começa automaticamente.\n"
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
        "🧙 *Passo 1/4: qual será o nome do personagem?*\nResponda com o nome ou use /cancelar.",
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
    estados(ctx)[estado_key(update)] = {"etapa": "raca", "personagem": {"nome": nome}}
    await update.message.reply_text(
        formatar_opcoes(RACAS, "🧬 *Passo 2/4: escolha a raça*"),
        parse_mode="Markdown", reply_markup=teclado_nomes(RACAS)
    )

async def receber_raca(update, ctx):
    escolha = update.message.text.strip()
    if escolha not in RACAS:
        await update.message.reply_text("⚠️ Escolha uma das raças exibidas.", reply_markup=teclado_nomes(RACAS))
        return
    estado = estados(ctx).get(estado_key(update))
    if not estado:
        await update.message.reply_text("⚠️ A criação expirou. Use /start novamente.")
        return
    estado["personagem"]["raca"] = escolha
    estado["etapa"] = "classe"
    await update.message.reply_text(
        formatar_opcoes(CLASSES, "⚔️ *Passo 3/4: escolha a classe*"),
        parse_mode="Markdown", reply_markup=teclado_nomes(CLASSES)
    )

async def receber_classe(update, ctx):
    escolha = update.message.text.strip()
    if escolha not in CLASSES:
        await update.message.reply_text("⚠️ Escolha uma das classes exibidas.", reply_markup=teclado_nomes(CLASSES))
        return
    estado = estados(ctx).get(estado_key(update))
    if not estado:
        await update.message.reply_text("⚠️ A criação expirou. Use /start novamente.")
        return
    estado["personagem"]["classe"] = escolha
    estado["etapa"] = "detalhes"
    await update.message.reply_text(
        "📝 *Passo 4/4: conte quem é esse personagem.*\n\n"
        "Escreva arquétipo, profissão, manias, medos, objetivos, aparência, passado, vínculos, segredos "
        "ou qualquer detalhe importante. Quanto mais contexto, mais personalizada será a história.\n\n"
        "Se quiser deixar a IA criar livremente, escreva nenhum.",
        parse_mode="Markdown", reply_markup=ForceReply(selective=True)
    )

async def finalizar_personagem(update, ctx, estado):
    p = estado["personagem"]
    await update.message.reply_text("🧙 Gerando atributos, ficha e história do personagem...")
    try:
        ficha = await narrator.criar_personagem(p["nome"], p["classe"], p["raca"], p.get("detalhes", ""))
        atributos = {**ATRIBUTOS_PADRAO, **ficha.get("atributos", {})}
        if not ficha.get("historia"):
            raise ValueError("ficha incompleta")
        chat_id = update.effective_chat.id
        sessao_existente = db.obter_sessao(chat_id)
        if sessao_existente:
            intro = {"titulo": "Campanha em andamento", "narrativa": "Você entrou na campanha existente. O Mestre mantém o estado atual da aventura.", "contexto": sessao_existente["contexto"]}
        else:
            intro = await narrator.iniciar_aventura(chat_id)
            db.criar_sessao(chat_id, intro["contexto"])
        db.salvar_personagem(update.effective_user.id, chat_id, p["nome"], p["classe"], p["raca"], atributos, ficha["historia"], p.get("detalhes", ""))
    except Exception:
        log.exception("Falha ao finalizar criação do personagem")
        await update.message.reply_text("⚠️ Não consegui finalizar a ficha agora. Seus dados continuam preservados; tente novamente.")
        return
    estados(ctx).pop(estado_key(update), None)
    personagem = {"nome": p["nome"], "raca": p["raca"], "classe": p["classe"], "atributos": atributos, "detalhes": p.get("detalhes", ""), "historia": ficha["historia"]}
    await update.message.reply_text(formatar_ficha_completa(personagem), reply_markup=ReplyKeyboardRemove())
    await enviar_texto_seguro(update, f"📚 *{intro['titulo']}*\n\n{intro['narrativa']}", parse_mode="Markdown")

async def receber_detalhes(update, ctx):
    estado = estados(ctx).get(estado_key(update))
    if not estado or "personagem" not in estado:
        await update.message.reply_text("⚠️ A criação expirou. Use /start novamente.")
        return
    detalhes = update.message.text.strip()
    estado["personagem"]["detalhes"] = "" if detalhes.lower() in {"nenhum", "nenhuma", "n/a", "nao", "não"} else detalhes[:4000]
    await finalizar_personagem(update, ctx, estado)

async def processar_entrada(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    etapa = estados(ctx).get(estado_key(update), {}).get("etapa")
    if etapa == "nome":
        await receber_nome(update, ctx)
    elif etapa == "raca":
        await receber_raca(update, ctx)
    elif etapa == "classe":
        await receber_classe(update, ctx)
    elif etapa == "detalhes":
        await receber_detalhes(update, ctx)

async def cancelar_entrada(update, ctx):
    estados(ctx).pop(estado_key(update), None)
    await update.message.reply_text("❌ Criação cancelada.", reply_markup=ReplyKeyboardRemove())

async def cmd_iniciar_historia(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ O fluxo atual é automático: depois dos detalhes, a ficha e a aventura são iniciadas.")

async def cmd_nova_aventura(update, ctx):
    chat_id = update.effective_chat.id
    if db.obter_sessao(chat_id) and (not ctx.args or ctx.args[0].upper() != "CONFIRMAR"):
        await update.message.reply_text(
            "⚠️ Isso encerra a campanha atual e apaga personagens e histórico. "
            "Se realmente quiser começar outra, use /nova_aventura CONFIRMAR."
        )
        return
    intro = await narrator.iniciar_aventura(chat_id)
    db.criar_sessao(chat_id, intro["contexto"], reset=True)
    await update.message.reply_text(
        f"🆕 Nova aventura criada: {intro['titulo']}\n\n"
        "Use /start para criar o personagem desta nova partida."
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
        try:
            cd = int(avaliacao.get("cd", 12))
        except (TypeError, ValueError):
            cd = 12
        cd = max(1, min(cd, 30))
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
    # Releia o estado após a chamada da IA: outro jogador pode ter agido durante o processamento.
    sessao_atual = db.obter_sessao(chat_id) or sessao
    historico = db.historico_recente(chat_id, limite=10)
    resultado = await narrator.narrar_acao_com_dado(sessao_atual, p, jogadores, acao, teste, historico)
    novo_ctx = resultado.get("novo_contexto") or sessao_atual["contexto"]
    if not db.atualizar_contexto(chat_id, novo_ctx, contexto_anterior=sessao_atual["contexto"]):
        # Estado mudou durante a narrativa. Não sobrescreva o estado do outro jogador.
        sessao_atual = db.obter_sessao(chat_id) or sessao_atual
        resultado = await narrator.narrar_acao_com_dado(sessao_atual, p, jogadores, acao, teste, db.historico_recente(chat_id, 10))
        novo_ctx = resultado.get("novo_contexto") or sessao_atual["contexto"]
        db.atualizar_contexto(chat_id, novo_ctx, contexto_anterior=sessao_atual["contexto"])
    db.registrar_acao(user_id, chat_id, acao, resultado["narrativa"])

    sugestoes_txt = formatar_sugestoes(resultado.get("sugestoes", []))
    texto = f"📖 {resultado['narrativa']}"
    if sugestoes_txt:
        texto += f"\n\n💡 *O que fazer agora?*\n{sugestoes_txt}"
    await enviar_texto_seguro(update, texto)


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
    cd = max(1, min(cd, 30))

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

    await enviar_texto_seguro(
        update,
        f"💡 Sugestões para {p['nome']}:\n\n" + "\n\n".join(linhas) +
        "\n\nUse /acao + descrição para agir!"
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
            caption=f"🏰 {resultado.get('descricao', '')}"[:1000],
        )
    else:
        await enviar_texto_seguro(update, f"🏰 Cena atual:\n\n{resultado.get('descricao', '')}")


# ─── /ficha ───────────────────────────────────────────────────────────────────

async def cmd_ficha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    p = db.obter_personagem(update.effective_user.id, update.effective_chat.id)
    if not p:
        await update.message.reply_text("❌ Você ainda não tem personagem. Use /start.")
        return
    await enviar_texto_seguro(update, formatar_ficha_completa(p))



# ─── /jogadores ───────────────────────────────────────────────────────────────

async def cmd_jogadores(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    jogadores = db.listar_jogadores(update.effective_chat.id)
    if not jogadores:
        await update.message.reply_text("👥 Nenhum jogador ainda.")
        return
    lista = "\n".join(f"• {j['nome']} — {j['classe']} {j['raca']}" for j in jogadores)
    await enviar_texto_seguro(update, f"👥 Jogadores ({len(jogadores)}):\n\n{lista}")


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
