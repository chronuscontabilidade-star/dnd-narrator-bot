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

try:
    from .database import Database
    from .dice import ATTR_EMOJI, detectar_atributo, escapa, formatar_resultado_dado, modificador, realizar_teste
    from .narrator import Narrator
    from .game.action import ActionResolver, movimento_permitido, normalize
    from .game.adventure import AdventureState
    from .game.combat import CombatState
    from .game.combat_flow import run_enemy_turns, start_pending_combat
except ImportError:
    from database import Database
    from dice import ATTR_EMOJI, detectar_atributo, escapa, formatar_resultado_dado, modificador, realizar_teste
    from narrator import Narrator
    from game.action import ActionResolver, movimento_permitido, normalize
    from game.adventure import AdventureState
    from game.combat import CombatState
    from game.combat_flow import run_enemy_turns, start_pending_combat

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
HIT_DICE_BY_CLASS = {"Guerreiro": 10, "Bárbaro": 12, "Ladino": 8, "Mago": 6, "Clérigo": 8, "Ranger": 10}
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

def action_locks(ctx):
    """Locks por chat para serializar ações que alteram a campanha."""
    return ctx.application.bot_data.setdefault("action_locks", {})


def _resolver_combate_aventura(aventura: dict) -> CombatState | None:
    """Reconstrói o combate ativo persistido, se houver."""
    raw = (aventura or {}).get("combate")
    if not raw:
        return None
    return CombatState.from_dict(raw)


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
        f"⚔️ Classe: {p.get('classe', '')} (Nível {p.get('nivel', 1)})\n"
        f"❤️ HP: {p.get('hp', 1)}/{p.get('hp_max', 1)}\n"
        f"🛡️ CA: {p.get('ca', 10)}\n\n"
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

        # Primeiro persistimos o personagem. A criação da ficha não depende
        # da existência de uma sessão antiga ou de uma aventura anterior.
        nivel = 1
        dado_vida = HIT_DICE_BY_CLASS.get(p["classe"], 8)
        hp_max = max(1, dado_vida + modificador(atributos.get("Constituição", 10)))
        ca = max(1, 10 + modificador(atributos.get("Destreza", 10)))

        db.salvar_personagem(
            update.effective_user.id,
            chat_id,
            p["nome"],
            p["classe"],
            p["raca"],
            atributos,
            ficha["historia"],
            p.get("detalhes", ""),
            nivel=nivel,
            hp_max=hp_max,
            hp=hp_max,
            ca=ca,
        )

        # Uma sessão só conta como campanha existente se tiver AdventureState
        # válido. Sessões antigas/incompletas não podem bloquear o início.
        sessao_existente = db.obter_sessao(chat_id)
        aventura_existente = sessao_existente.get("aventura") if sessao_existente else None
        if aventura_existente:
            intro = {
                "titulo": aventura_existente.get("aventura", {}).get("titulo", "Campanha em andamento"),
                "narrativa": (
                    "Você entra na aventura já em andamento. "
                    "O Mestre mantém o mundo e o progresso atuais."
                ),
                "contexto": sessao_existente["contexto"],
            }
        else:
            await update.message.reply_text("📚 Criando uma nova aventura para o grupo...")
            intro = await narrator.iniciar_aventura(chat_id)
            db.criar_sessao(chat_id, intro["contexto"], aventura=intro)

        estados(ctx).pop(estado_key(update), None)
        personagem = {
            "nome": p["nome"],
            "raca": p["raca"],
            "classe": p["classe"],
            "nivel": nivel,
            "hp_max": hp_max,
            "hp": hp_max,
            "ca": ca,
            "atributos": atributos,
            "detalhes": p.get("detalhes", ""),
            "historia": ficha["historia"],
        }
        await update.message.reply_text(
            formatar_ficha_completa(personagem),
            reply_markup=ReplyKeyboardRemove(),
        )

        # A introdução é texto gerado pela IA. Não use Markdown aqui.
        await enviar_texto_seguro(
            update,
            f"📚 {intro['titulo']}\n\n{intro['narrativa']}",
        )
        await update.message.reply_text(
            "🎲 A aventura começou. Quando estiver pronto, use /acao seguido do que seu personagem faz."
        )
        return
    except Exception:
        log.exception("Falha ao finalizar criação do personagem")
        await update.message.reply_text(
            "⚠️ Não consegui iniciar a aventura agora. A ficha foi preservada. "
            "Use /iniciar_historia para tentar iniciar a campanha novamente."
        )
        return

async def receber_detalhes(update, ctx):
    estado = estados(ctx).get(estado_key(update))
    if not estado or "personagem" not in estado:
        await update.message.reply_text("⚠️ A criação expirou. Use /start novamente.")
        return
    detalhes = update.message.text.strip()
    estado["personagem"]["detalhes"] = "" if detalhes.lower() in {"nenhum", "nenhuma", "n/a", "nao", "não"} else detalhes[:4000]

    # A finalização cria/reativa a campanha e persiste personagem + sessão.
    # Ela precisa usar o mesmo lock por chat de /acao e /nova_aventura.
    chat_id = update.effective_chat.id
    lock = action_locks(ctx).setdefault(chat_id, asyncio.Lock())
    async with lock:
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
    """Inicia/repara a aventura para um personagem já criado.

    A operação inteira fica serializada por chat para impedir que duas
    inicializações concorrentes sobrescrevam a sessão da campanha.
    """
    chat_id = update.effective_chat.id
    lock = action_locks(ctx).setdefault(chat_id, asyncio.Lock())
    async with lock:
        return await _cmd_iniciar_historia_locked(update, ctx)

async def _cmd_iniciar_historia_locked(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    personagem = db.obter_personagem(user_id, chat_id)
    if not personagem:
        await update.message.reply_text("❌ Crie seu personagem primeiro com /start.")
        return

    sessao = db.obter_sessao(chat_id)
    if sessao and sessao.get("aventura"):
        aventura = sessao["aventura"]
        titulo = aventura.get("aventura", {}).get("titulo", "Campanha em andamento")
        await update.message.reply_text(
            f"📚 A aventura já está ativa: {titulo}\n\nUse /acao para jogar."
        )
        return

    try:
        await update.message.reply_text("📚 Gerando a aventura...")
        intro = await narrator.iniciar_aventura(chat_id)
        db.criar_sessao(chat_id, intro["contexto"], aventura=intro)
        await enviar_texto_seguro(
            update,
            f"📚 {intro['titulo']}\n\n{intro['narrativa']}",
        )
        await update.message.reply_text(
            "🎲 A aventura começou. Use /acao seguido do que seu personagem faz."
        )
    except Exception:
        log.exception("Falha ao iniciar aventura manualmente")
        await update.message.reply_text(
            "⚠️ Não consegui iniciar a aventura agora. Tente novamente em alguns segundos."
        )

async def cmd_nova_aventura(update, ctx):
    """Cria uma nova campanha com a mesma serialização usada por /acao."""
    chat_id = update.effective_chat.id
    lock = action_locks(ctx).setdefault(chat_id, asyncio.Lock())
    async with lock:
        return await _cmd_nova_aventura_locked(update, ctx)

async def _cmd_nova_aventura_locked(update, ctx):
    chat_id = update.effective_chat.id
    if db.obter_sessao(chat_id) and (not ctx.args or ctx.args[0].upper() != "CONFIRMAR"):
        await update.message.reply_text(
            "⚠️ Isso encerra a campanha atual e apaga personagens e histórico. "
            "Se realmente quiser começar outra, use /nova_aventura CONFIRMAR."
        )
        return
    intro = await narrator.iniciar_aventura(chat_id)
    db.criar_sessao(chat_id, intro["contexto"], reset=True, aventura=intro)
    await update.message.reply_text(
        f"🆕 Nova aventura criada: {intro['titulo']}\n\n"
        "Use /start para criar o personagem desta nova partida."
    )


# ─── /acao — intenção determinística + narrativa ─────────────────────────────

async def cmd_acao(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lock = action_locks(ctx).setdefault(chat_id, asyncio.Lock())
    async with lock:
        return await _cmd_acao_locked(update, ctx)

async def _cmd_acao_locked(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    sessao = db.obter_sessao(chat_id)
    p = db.obter_personagem(user_id, chat_id)

    if not sessao or not p:
        await update.message.reply_text("❌ Inicie a história com /start e /iniciar_historia.")
        return

    acao = " ".join(ctx.args).strip() if ctx.args else ""
    if not acao:
        await update.message.reply_text(
            "Use /acao seguido da descrição.\n"
            "Ex: /acao Tento roubar o cálice sem ninguém ver"
        )
        return

    aventura_atual = sessao.get("aventura") or {}
    intent = ActionResolver(aventura_atual).resolve(acao)

    # O resolver define a natureza da ação. O narrador não pode transformar
    # uma ação rotineira em rolagem arbitrariamente.
    teste = None
    combate = None
    if intent.tipo == "fim_turno":
        combate = _resolver_combate_aventura(aventura_atual) if aventura_atual.get("combate") else None
        if combate is None or not combate.started:
            await update.message.reply_text("⚔️ Não há combate ativo.")
            return
        atacante = next((c for c in combate.combatants if c.name == p["nome"] and c.is_player), None)
        if atacante is None:
            await update.message.reply_text("⚔️ Seu personagem não está presente no combate ativo.")
            return
        try:
            proximo = combate.end_turn(atacante)
        except (RuntimeError, ValueError) as exc:
            await update.message.reply_text(f"⚔️ Não foi possível encerrar o turno: {exc}")
            return

        inimigo_resultados = run_enemy_turns(combate)
        raw_combate = combate.to_dict()
        raw_combate["encounter_id"] = (aventura_atual.get("combate") or {}).get("encounter_id")
        aventura_atual = dict(aventura_atual)
        aventura_atual["combate"] = raw_combate
        if combate.finished:
            encounter_id = raw_combate.get("encounter_id")
            if encounter_id:
                try:
                    aventura_atual = AdventureState.from_dict(aventura_atual).complete_encounter(encounter_id).to_dict()
                except ValueError:
                    pass
            aventura_atual.pop("combate", None)

        if combate.finished:
            linhas = ["🏁 O combate terminou."]
        else:
            linhas = [f"⏳ Turno encerrado. Agora é a vez de {combate.current.name}."]
        for item in inimigo_resultados:
            status = "acertou" if item["acertou"] else "errou"
            detalhe = f", causando {item['dano']} de dano." if item["acertou"] else "."
            linhas.append(f"⚔️ {item['inimigo']} {status} {item['alvo']}{detalhe}")
        await update.message.reply_text("\n".join(linhas))
        teste = {"tipo": "turno", "sucesso": True}
    elif intent.tipo == "ataque":
        try:
            combate = _resolver_combate_aventura(aventura_atual)
        except (ValueError, TypeError, KeyError) as exc:
            log.warning("Combate persistido inválido: %s", exc)
            combate = None

        if combate is None or not combate.started:
            jogadores = db.listar_jogadores(chat_id)
            combate, _ = start_pending_combat(aventura_atual, jogadores)
            if combate is None or not combate.started:
                await update.message.reply_text(
                    "⚔️ Não há combate ativo nem encontro de combate pendente neste local."
                )
                return
            # Se o inimigo venceu a iniciativa, o motor resolve os turnos
            # inimigos até devolver o controle ao primeiro jogador.
            if combate.started and not combate.finished and not combate.current.is_player:
                run_enemy_turns(combate)
            if combate.finished or not combate.current.is_player:
                await update.message.reply_text("⚔️ O combate começou, mas nenhum jogador está apto a agir agora.")
                return

        atacante = next((c for c in combate.combatants if c.name == p["nome"] and c.is_player), None)
        alvo_nome = intent.alvo
        if not alvo_nome:
            texto_normalizado = normalize(acao)
            alvo_nome = next(
                (c.name for c in combate.combatants
                 if c.is_alive and normalize(c.name) in texto_normalizado and not c.is_player),
                None,
            )
        alvo = next(
            (c for c in combate.combatants if alvo_nome and normalize(c.name) == normalize(alvo_nome)),
            None,
        )
        if atacante is None:
            await update.message.reply_text("⚔️ Seu personagem não está presente no combate ativo.")
            return
        if alvo is None:
            await update.message.reply_text(
                "⚔️ Não identifiquei o alvo. Diga o nome do inimigo, por exemplo: "
                "/acao atacar Goblin."
            )
            return

        try:
            resultado_ataque = combate.attack(atacante, alvo)
        except (RuntimeError, ValueError) as exc:
            await update.message.reply_text(f"⚔️ Ataque recusado pelo motor: {exc}")
            return

        teste = {
            "tipo": "ataque",
            "sucesso": resultado_ataque.hit,
            "critico": resultado_ataque.critical,
            "falha_critica": resultado_ataque.fumble,
            "rolagem": resultado_ataque.roll.total,
            "ca": resultado_ataque.armor_class,
            "dano": resultado_ataque.damage,
            "alvo": resultado_ataque.target,
            "hp_alvo": alvo.hp,
        }
        aventura_atual = dict(aventura_atual)
        raw_combate = combate.to_dict()
        raw_combate["encounter_id"] = (aventura_atual.get("combate") or {}).get("encounter_id")
        aventura_atual["combate"] = raw_combate
        if combate.finished:
            encounter_id = raw_combate.get("encounter_id")
            if encounter_id:
                try:
                    aventura_atual = AdventureState.from_dict(aventura_atual).complete_encounter(encounter_id).to_dict()
                except ValueError:
                    pass
            aventura_atual.pop("combate", None)
        sessao_atual = dict(sessao)
        sessao_atual["aventura"] = aventura_atual
        await update.message.reply_text(
            f"⚔️ {'CRÍTICO' if resultado_ataque.critical else 'ACERTO' if resultado_ataque.hit else 'FALHA'} "
            f"| {resultado_ataque.roll.total} vs CA {resultado_ataque.armor_class}"
            + (f" | dano {resultado_ataque.damage} | HP {alvo.hp}" if resultado_ataque.hit else "")
        )
    elif intent.requer_teste:
        atributo = intent.atributo
        if atributo and atributo not in p["atributos"]:
            atributo = "Destreza"
        if atributo:
            cd = max(1, min(int(intent.cd or 12), 30))
            teste = realizar_teste(p["atributos"], atributo, dificuldade=cd)
            await update.message.reply_text(
                formatar_resultado_dado(teste, p["nome"]), parse_mode="MarkdownV2"
            )

    await update.message.reply_text("📖 O narrador descreve o que acontece...")

    jogadores = db.listar_jogadores(chat_id)
    sessao_atual = db.obter_sessao(chat_id) or sessao
    sessao_atual["aventura"] = aventura_atual
    historico = db.historico_recente(chat_id, limite=10)

    resultado = await narrator.narrar_acao_com_dado(
        sessao_atual, p, jogadores, acao, teste, historico
    )

    # Atualiza somente fatos que o motor conseguiu validar.
    try:
        estado = AdventureState.from_dict(sessao_atual.get("aventura") or aventura_atual)
        progresso = estado.data["progresso"]
        local_atual = progresso.get("local_atual")

        resultado_evento = (
            "sucesso" if teste and teste.get("sucesso")
            else "falha" if teste else "sem teste"
        )
        estado = estado.update_progress(
            event={
                "tipo": "acao_jogador",
                "jogador": p["nome"],
                "acao": acao,
                "resultado": resultado_evento,
            },
        )

        # A progressão da cena é estado de jogo, não apenas texto de contexto.
        # Isso impede que o fallback volte para o mesmo beat narrativo a cada ação.
        progresso_atual = estado.data["progresso"]
        progresso_atual["etapa_cena"] = int(progresso_atual.get("etapa_cena", 0) or 0) + 1

        if intent.tipo == "movimento":
            locais = estado.data.get("locais", [])
            destino = next((l for l in locais if l.get("id") == intent.destino), None) if intent.destino else None

            # "entrar/acessar" sem nome de destino pode avançar para a próxima
            # área conectada descoberta pelo mapa, mas nunca salta para um local
            # arbitrariamente distante.
            if destino is None and any(
                termo in normalize(acao)
                for termo in ("entrar", "acessar")
            ):
                local_atual = progresso_atual.get("local_atual")
                atual = next((l for l in locais if l.get("id") == local_atual), None)
                proximo = next(
                    (
                        l for l in locais
                        if l.get("id") in (atual or {}).get("conexoes", [])
                        and not l.get("descoberto")
                    ),
                    None,
                )
                destino = proximo

            if destino and movimento_permitido(estado.to_dict(), destino["id"]):
                estado = estado.update_progress(
                    current_location=destino["id"],
                    discovered_location=destino["id"],
                    visited_location=destino["id"],
                    event={
                        "tipo": "movimento",
                        "descricao": f"{p['nome']} foi para {destino.get('nome')}.",
                    },
                )

        elif intent.tipo in {"investigacao", "percepcao"} and (
            not teste or teste.get("sucesso")
        ):
            locais = estado.data.get("locais", [])
            atual = next((l for l in locais if l.get("id") == local_atual), None)
            conexoes = (atual or {}).get("conexoes", [])
            alvo = next(
                (l for l in locais if l.get("id") in conexoes and not l.get("descoberto")),
                None,
            )
            if alvo:
                estado = estado.update_progress(
                    discovered_location=alvo["id"],
                    event={
                        "tipo": "descoberta",
                        "descricao": f"{p['nome']} descobriu {alvo.get('nome')}.",
                    },
                )

        aventura_nova = estado.to_dict()
    except (ValueError, TypeError, KeyError) as exc:
        log.warning("Não foi possível atualizar AdventureState: %s", exc)
        aventura_nova = sessao_atual.get("aventura") or aventura_atual

    novo_ctx = resultado.get("novo_contexto") or sessao_atual["contexto"]
    if novo_ctx.strip() == sessao_atual["contexto"].strip():
        status = (
            "sucesso" if teste and teste.get("sucesso")
            else "falha" if teste else "resultado narrativo"
        )
        novo_ctx = (
            f"{sessao_atual['contexto']}\n"
            f"Evento: {p['nome']} realizou '{acao}'. Resultado: {status}."
        )

    contexto_ok = db.atualizar_estado_campanha(
        chat_id,
        novo_ctx,
        aventura_nova,
        contexto_anterior=sessao_atual["contexto"],
    )
    if not contexto_ok:
        # Outra operação modificou a sessão depois do snapshot. O lock evita
        # concorrência dentro do processo, mas o CAS também protege contra
        # múltiplas instâncias do bot.
        log.warning("CAS rejeitou atualização de contexto no chat %s", chat_id)
        await update.message.reply_text(
            "⚠️ A campanha mudou enquanto eu processava sua ação. "
            "Sua ação não foi aplicada ao contexto atual. Tente novamente."
        )
        return
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
    lista = "\n".join(f"• *{j['nome']}* — {j['classe']} {j['raca']}" for j in jogadores)
    await update.message.reply_text(
        f"👥 *Jogadores ({len(jogadores)}):*\n\n{lista}",
        parse_mode="Markdown",
    )


# ─── Setup de comandos ────────────────────────────────────────────────────────

async def configurar_comandos(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Criar personagem"),
        BotCommand("iniciar_historia", "Finalizar ficha e iniciar história"),
        BotCommand("acao", "Fazer uma ação na aventura"),
        BotCommand("rolar", "Rolar dado livremente"),
        BotCommand("sugerir", "Sugestões de ação para seu personagem"),
        BotCommand("cena", "Descrever a cena atual"),
        BotCommand("ficha", "Ver sua ficha de personagem"),
        BotCommand("jogadores", "Listar jogadores na sessão"),
        BotCommand("ajuda", "Mostrar todos os comandos"),
        BotCommand("entrar", "Recriar personagem"),
        BotCommand("cancelar", "Cancelar criação de personagem"),
        BotCommand("nova_aventura", "Começar uma nova campanha"),
    ])


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN não encontrado no .env!")

    proxy = os.getenv("TELEGRAM_PROXY") or None
    req_kwargs = dict(
        connect_timeout=30,
        read_timeout=60,
        write_timeout=30,
        pool_timeout=30,
        proxy=proxy,
    )
    request = HTTPXRequest(connection_pool_size=8, **req_kwargs)
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
        commands = [
            ("start", cmd_start),
            ("ajuda", cmd_ajuda),
            ("entrar", cmd_entrar),
            ("iniciar_historia", cmd_iniciar_historia),
            ("cancelar", cancelar_entrada),
            ("nova_aventura", cmd_nova_aventura),
            ("acao", cmd_acao),
            ("rolar", cmd_rolar),
            ("sugerir", cmd_sugerir),
            ("cena", cmd_cena),
            ("ficha", cmd_ficha),
            ("jogadores", cmd_jogadores),
        ]
        for command, handler in commands:
            app.add_handler(CommandHandler(command, handler))
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
