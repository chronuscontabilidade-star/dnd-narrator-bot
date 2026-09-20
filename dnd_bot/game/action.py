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

    def resolve(self, action: str) -> ActionIntent:
        text = (action or "").strip()
        n = normalize(text)

        if not text:
            return ActionIntent("invalida", text, motivo="Ação vazia.")

        destination = self._find_location(text)

        # Movimento explícito. Entrar/ir por uma passagem livre não é teste.
        movement_words = (
            "entrar", "entra", "entro", "ir para", "vou para", "ir ate",
            "vou ate", "seguir para", "seguir ate", "voltar para", "sair",
            "caminhar para", "andar para", "aproximar",
        )
        if any(word in n for word in movement_words):
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

        if any(word in n for word in ("atacar", "bater", "golpear", "lutar")):
            return ActionIntent(
                tipo="ataque",
                descricao=text,
                requer_teste=True,
                motivo="Ataques são resolvidos pelo motor de combate.",
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
