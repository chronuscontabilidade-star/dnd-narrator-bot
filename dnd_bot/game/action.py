"""Resolvedor determinístico de intenções de ação para D&D 5e 2014.

A linguagem do jogador é livre, mas ações óbvias são convertidas em uma
intenção estruturada antes de chegar ao narrador. A IA pode narrar e ajudar
em casos ambíguos, mas não decide fatos mecânicos do mundo.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata


SKILLS = {
    "Acrobacia": "Destreza",
    "Adestrar Animais": "Sabedoria",
    "Arcanismo": "Inteligência",
    "Atletismo": "Força",
    "Atuação": "Carisma",
    "Enganação": "Carisma",
    "Furtividade": "Destreza",
    "História": "Inteligência",
    "Intuição": "Sabedoria",
    "Intimidação": "Carisma",
    "Investigação": "Inteligência",
    "Medicina": "Sabedoria",
    "Natureza": "Inteligência",
    "Percepção": "Sabedoria",
    "Persuasão": "Carisma",
    "Prestidigitação": "Destreza",
    "Religião": "Inteligência",
    "Sobrevivência": "Sabedoria",
}


@dataclass(frozen=True)
class ActionIntent:
    tipo: str
    descricao: str
    alvo: str | None = None
    destino: str | None = None
    habilidade: str | None = None
    atributo: str | None = None
    requer_teste: bool = False
    cd: int | None = None
    motivo: str = ""


def normalize(texto: str) -> str:
    valor = (texto or "").lower()
    return "".join(
        ch for ch in unicodedata.normalize("NFD", valor)
        if unicodedata.category(ch) != "Mn"
    )


def movimento_permitido(adventure: dict, destino_id: str) -> bool:
    """Valida movimento como conexão direta no grafo da aventura."""
    progresso = adventure.get("progresso", {})
    local_atual = progresso.get("local_atual")
    locais = adventure.get("locais", [])
    atual = next((local for local in locais if local.get("id") == local_atual), None)
    destino = next((local for local in locais if local.get("id") == destino_id), None)
    if not atual or not destino:
        return False
    return destino_id == local_atual or destino_id in atual.get("conexoes", [])


class ActionResolver:
    """Resolve ações comuns sem depender de Telegram, DB ou provedor de IA."""

    def __init__(self, adventure: dict | None = None):
        self.adventure = adventure or {}

    def _find_location(self, text: str) -> str | None:
        normalized = normalize(text)
        locais = self.adventure.get("locais", [])
        # Primeiro tenta nome completo, depois tokens suficientemente distintos.
        for local in locais:
            nome = local.get("nome", "")
            if nome and normalize(nome) in normalized:
                return local.get("id")
        return None

    def _skill(self, skill: str, *, alvo=None, cd=12, motivo="") -> ActionIntent:
        return ActionIntent(
            tipo="teste",
            descricao="",
            alvo=alvo,
            habilidade=skill,
            atributo=SKILLS[skill],
            requer_teste=True,
            cd=cd,
            motivo=motivo,
        )


    def resolve_semantic(self, action: str, semantic: dict) -> ActionIntent:
        """Converte uma intenção semântica validada pela IA em regra determinística.

        A IA pode classificar a intenção e indicar referências linguísticas,
        mas não escolhe CD, rolagem, dano ou consequências do jogo.
        """
        text = (action or "").strip()
        tipo = str((semantic or {}).get("tipo") or "").strip().lower()
        alvo = (semantic or {}).get("alvo")
        destino = (semantic or {}).get("destino")

        allowed = {
            "movimento", "percepcao", "investigacao", "obstaculo",
            "ferramentas", "furtividade", "furto", "social",
            "ataque", "narrativa", "fim_turno",
        }
        if tipo not in allowed:
            return ActionIntent("ambigua", text, motivo="Intenção semântica não reconhecida.")

        if destino:
            destino = str(destino)
            if not any(local.get("id") == destino for local in self.adventure.get("locais", [])):
                destino = None

        if tipo == "narrativa":
            # A classificação semântica pode chamar de "narrativa" uma ação que
            # claramente muda a posição do personagem. O motor corrige isso aqui,
            # porque deslocamento é mecânica de estado, não apenas prosa.
            n = normalize(text)
            termos_movimento = (
                "descer", "subir", "atravessar", "cruzar", "aproximar",
                "aproximar-se", "afastar", "recuar", "avancar", "avançar",
                "seguir", "continuar", "entrar", "sair", "voltar", "retornar",
                "caminhar", "andar", "ir para", "ir pra", "vou para", "vou pra",
            )
            if any(termo in n for termo in termos_movimento):
                tipo = "movimento"

        if tipo == "movimento":
            # Referências como "seguir as pegadas", "continuar pela passagem" ou
            # "avançar pelo caminho" podem apontar para a próxima conexão do mapa
            # sem o jogador conhecer o ID/nome formal do local.
            if destino is None:
                referencia = normalize(str((semantic or {}).get("referencia") or ""))
                termos_rota = (
                    "rota", "caminho", "passagem", "pegada", "trilha",
                    "corredor", "estrada", "seguir", "avancar", "avançar",
                    "descer", "subir", "atravessar", "cruzar", "aproximar",
                    "afastar", "recuar", "retornar", "entrar", "sair",
                    "caminhar", "andar", "ir para", "ir pra", "vou para", "vou pra",
                )
                if any(termo in referencia or termo in normalize(text) for termo in termos_rota):
                    atual_id = (self.adventure.get("progresso") or {}).get("local_atual")
                    atual = next(
                        (local for local in self.adventure.get("locais", [])
                         if local.get("id") == atual_id),
                        None,
                    )
                    conexoes = (atual or {}).get("conexoes", [])
                    destino = next(
                        (
                            local.get("id")
                            for local in self.adventure.get("locais", [])
                            if local.get("id") in conexoes and not local.get("descoberto")
                        ),
                        None,
                    )
            return ActionIntent(
                tipo="movimento", descricao=text, alvo=str(alvo) if alvo else None,
                destino=destino, requer_teste=False,
                motivo="Intenção de movimento identificada semanticamente; o motor valida o destino.",
            )
        if tipo == "percepcao":
            return ActionIntent("percepcao", text, alvo=str(alvo) if alvo else None,
                                habilidade="Percepção", atributo="Sabedoria",
                                requer_teste=True, cd=12,
                                motivo="Ação de percepção identificada semanticamente.")
        if tipo == "investigacao":
            return ActionIntent("investigacao", text, alvo=str(alvo) if alvo else None,
                                habilidade="Investigação", atributo="Inteligência",
                                requer_teste=True, cd=12,
                                motivo="Ação de investigação identificada semanticamente.")
        if tipo == "obstaculo":
            return ActionIntent("obstaculo", text, alvo=str(alvo) if alvo else None,
                                habilidade="Atletismo", atributo="Força",
                                requer_teste=True, cd=12,
                                motivo="Superação física identificada semanticamente.")
        if tipo == "ferramentas":
            return ActionIntent("ferramentas", text, alvo=str(alvo) if alvo else "fechadura",
                                habilidade=None, atributo=None,
                                requer_teste=True, cd=12,
                                motivo="Uso de ferramenta identificado semanticamente.")
        if tipo == "furtividade":
            return ActionIntent("furtividade", text, alvo=str(alvo) if alvo else None,
                                habilidade="Furtividade", atributo="Destreza",
                                requer_teste=True, cd=12,
                                motivo="Furtividade identificada semanticamente.")
        if tipo == "furto":
            return ActionIntent("furto", text, alvo=str(alvo) if alvo else None,
                                habilidade="Prestidigitação", atributo="Destreza",
                                requer_teste=True, cd=12,
                                motivo="Tentativa de furto identificada semanticamente.")
        if tipo == "social":
            habilidade = str((semantic or {}).get("habilidade") or "Persuasão")
            if habilidade not in SKILLS or SKILLS[habilidade] != "Carisma":
                habilidade = "Persuasão"
            return ActionIntent("social", text, alvo=str(alvo) if alvo else None,
                                habilidade=habilidade, atributo="Carisma",
                                requer_teste=True, cd=12,
                                motivo="Interação social identificada semanticamente.")
        if tipo == "ataque":
            return ActionIntent("ataque", text, alvo=str(alvo) if alvo else None,
                                requer_teste=False,
                                motivo="Ataque identificado semanticamente; o motor de combate resolve a mecânica.")
        if tipo == "fim_turno":
            return ActionIntent("fim_turno", text, requer_teste=False,
                                motivo="Encerramento de turno identificado semanticamente.")
        return ActionIntent("narrativa", text, alvo=str(alvo) if alvo else None,
                            destino=destino, requer_teste=False,
                            motivo="Ação narrativa identificada semanticamente.")

    def resolve(self, action: str) -> ActionIntent:
        text = (action or "").strip()
        n = normalize(text)

        if not text:
            return ActionIntent("invalida", text, motivo="Ação vazia.")

        destination = self._find_location(text)

        # Movimento explícito. Entrar/ir/avançar por uma rota livre não é teste.
        movement_words = (
            "entrar", "entra", "entro", "ir para", "vou para", "ir pra", "vou pra", "ir ate",
            "vou ate", "seguir para", "seguir pra", "seguir ate", "seguir pela", "seguir pelo",
            "avancar", "avancar pela", "avancar pelo", "avançar", "avançar pela", "avançar pelo",
            "voltar para", "voltar pra", "sair", "caminhar para", "andar para", "aproximar",
        )
        if any(word in n for word in movement_words):
            # Quando o jogador não nomeia o destino, uma expressão como
            # "avançar pela rota descoberta" deve consumir a próxima conexão
            # direta ainda não descoberta. Nunca escolhemos um local distante.
            if destination is None and any(
                termo in n for termo in ("avancar", "seguir pela", "seguir pelo", "rota", "passagem", "caminho")
            ):
                atual = next(
                    (local for local in self.adventure.get("locais", [])
                     if local.get("id") == self.adventure.get("progresso", {}).get("local_atual")),
                    None,
                )
                conexoes = (atual or {}).get("conexoes", [])
                destination = next(
                    (local.get("id") for local in self.adventure.get("locais", [])
                     if local.get("id") in conexoes and not local.get("descoberto")),
                    None,
                )
            return ActionIntent(
                tipo="movimento",
                descricao=text,
                destino=destination,
                requer_teste=False,
                motivo="Movimento rotineiro; o motor valida se o destino é acessível.",
            )

        # Percepção: notar/ouvir algo oculto é diferente de apenas olhar.
        perception_words = (
            "ouvir", "escutar", "atentar aos sons", "perceber",
            "notar", "detectar", "ver se tem", "observar atentamente",
            "procurar ouvir",
        )
        if any(word in n for word in perception_words):
            return ActionIntent(
                tipo="percepcao",
                descricao=text,
                habilidade="Percepção",
                atributo=SKILLS["Percepção"],
                requer_teste=True,
                cd=12,
                motivo="Ação tenta perceber algo que pode estar oculto.",
            )

        # Investigação é usada para interpretar pistas, mecanismos e detalhes.
        investigation_words = (
            "investigar", "procurar", "buscar pistas", "inspecionar",
            "analisar", "examinar", "explorar",
        )
        if any(word in n for word in investigation_words):
            return ActionIntent(
                tipo="investigacao",
                descricao=text,
                habilidade="Investigação",
                atributo=SKILLS["Investigação"],
                requer_teste=True,
                cd=12,
                motivo="Ação busca ou interpreta pistas e detalhes.",
            )

        if any(word in n for word in ("arrombar", "forcar a porta", "forcar porta", "empurrar a porta")):
            return ActionIntent(
                tipo="obstaculo",
                descricao=text,
                habilidade="Atletismo",
                atributo="Força",
                requer_teste=True,
                cd=12,
                motivo="Superar fisicamente um obstáculo.",
            )

        if any(word in n for word in ("abrir fechadura", "destrancar", "usar gazua", "usar gazuas")):
            return ActionIntent(
                tipo="ferramentas",
                descricao=text,
                alvo="fechadura",
                requer_teste=True,
                cd=12,
                motivo="Ação depende de ferramentas de ladrão e proficiência quando aplicável.",
            )

        if any(word in n for word in ("esconder", "furtividade", "me ocultar", "me esconder")):
            return ActionIntent(
                tipo="furtividade",
                descricao=text,
                habilidade="Furtividade",
                atributo="Destreza",
                requer_teste=True,
                cd=12,
                motivo="Tentar permanecer não detectado.",
            )

        if any(word in n for word in ("roubar", "furtar", "pegar sem ser visto", "surrupiar")):
            return ActionIntent(
                tipo="furto",
                descricao=text,
                habilidade="Prestidigitação",
                atributo="Destreza",
                requer_teste=True,
                cd=12,
                motivo="Tentar pegar algo sem ser percebido.",
            )

        social = (
            ("persuadir", "Persuasão"),
            ("convencer", "Persuasão"),
            ("negociar", "Persuasão"),
            ("enganar", "Enganação"),
            ("mentir", "Enganação"),
            ("blefar", "Enganação"),
            ("intimidar", "Intimidação"),
            ("ameaçar", "Intimidação"),
        )
        for word, skill in social:
            if word in n:
                return ActionIntent(
                    tipo="social",
                    descricao=text,
                    habilidade=skill,
                    atributo=SKILLS[skill],
                    requer_teste=True,
                    cd=12,
                    motivo=f"Interação social que depende de {skill}.",
                )

        if any(word in n for word in ("encerrar turno", "terminar turno", "fim do turno", "passar turno")):
            return ActionIntent(
                tipo="fim_turno",
                descricao=text,
                requer_teste=False,
                motivo="Encerramento explícito do turno de combate.",
            )

        if any(word in n for word in ("atacar", "bater", "golpear", "lutar")):
            alvo = None
            combate = self.adventure.get("combate") or {}
            for combatant in combate.get("combatants", []):
                nome = combatant.get("name", "")
                if nome and normalize(nome) in n:
                    alvo = nome
                    break
            return ActionIntent(
                tipo="ataque",
                descricao=text,
                alvo=alvo,
                requer_teste=False,
                motivo="Ataques são resolvidos exclusivamente pelo motor de combate.",
            )

        if any(word in n for word in ("escalar", "subir pela parede")):
            return ActionIntent(
                tipo="obstaculo",
                descricao=text,
                habilidade="Atletismo",
                atributo="Força",
                requer_teste=True,
                cd=12,
                motivo="Escalada pode exigir teste quando houver risco.",
            )

        if any(word in n for word in ("saltar", "pular")):
            return ActionIntent(
                tipo="obstaculo",
                descricao=text,
                habilidade="Atletismo",
                atributo="Força",
                requer_teste=True,
                cd=12,
                motivo="Salto pode exigir teste quando houver risco relevante.",
            )

        # Desafios, provocações e convites para confronto são intenções sociais,
        # mesmo quando a frase começa com uma ação narrativa como "olhar".
        challenge_words = (
            "chamar para briga", "chamar pra briga", "desafiar para briga",
            "desafiar pra briga", "desafiar", "provocar uma briga",
            "provocar", "chamar para lutar", "chamar pra lutar",
            "convidar para lutar", "convidar pra lutar", "ameacar de briga",
        )
        if any(word in n for word in challenge_words) or ("chamar" in n and "briga" in n) or ("desafiar" in n and ("lutar" in n or "briga" in n)):
            return ActionIntent(
                tipo="social",
                descricao=text,
                habilidade="Intimidação",
                atributo="Carisma",
                requer_teste=True,
                cd=12,
                motivo="Provocar ou desafiar alguém pode exigir Intimidação.",
            )

        # Ações puramente narrativas.
        if any(word in n for word in (
            "andar", "caminhar", "olhar", "observar", "ver", "falar",
            "dizer", "perguntar", "responder", "sentar", "levantar",
            "esperar", "continuar", "parar", "respirar",
        )):
            return ActionIntent(
                tipo="narrativa",
                descricao=text,
                requer_teste=False,
                motivo="Ação rotineira sem incerteza relevante.",
            )

        # Ambígua: o narrador pode descrever, mas não recebe autorização
        # para inventar uma rolagem. O padrão seguro é não bloquear o jogador.
        return ActionIntent(
            tipo="ambigua",
            descricao=text,
            requer_teste=False,
            motivo="Ação não classificada; nenhum teste é imposto automaticamente.",
        )


__all__ = ["ActionIntent", "ActionResolver", "SKILLS", "normalize", "movimento_permitido"]
