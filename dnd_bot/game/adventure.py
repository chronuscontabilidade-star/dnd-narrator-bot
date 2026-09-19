"""Estado estruturado e transitório de uma aventura gerada pela IA.

O objetivo não é armazenar uma aventura pré-escrita. Cada nova campanha recebe
um mundo novo gerado em tempo de execução. Este módulo apenas define o formato
mínimo que a IA deve seguir para que o Game Engine consiga acompanhar o mundo.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
import json


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AdventureState:
    """Representação validada do estado estruturado da campanha."""

    data: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AdventureState":
        if not isinstance(raw, dict):
            raise ValueError("AdventureState precisa ser um objeto JSON")

        adventure = raw.get("aventura")
        if not isinstance(adventure, dict):
            raise ValueError("Campo 'aventura' ausente ou inválido")

        required = ("id", "titulo", "resumo", "status")
        if any(not adventure.get(key) for key in required):
            raise ValueError("Metadados da aventura incompletos")

        for key in ("mundo", "locais", "npcs", "encounters", "quests", "itens", "flags", "progresso"):
            if key not in raw:
                raise ValueError(f"Campo obrigatório ausente: {key}")

        if not isinstance(raw["locais"], list):
            raise ValueError("'locais' precisa ser uma lista")
        if not isinstance(raw["npcs"], list):
            raise ValueError("'npcs' precisa ser uma lista")
        if not isinstance(raw["encounters"], list):
            raise ValueError("'encounters' precisa ser uma lista")
        if not isinstance(raw["quests"], list):
            raise ValueError("'quests' precisa ser uma lista")
        if not isinstance(raw["itens"], list):
            raise ValueError("'itens' precisa ser uma lista")
        if not isinstance(raw["flags"], dict):
            raise ValueError("'flags' precisa ser um objeto")
        if not isinstance(raw["progresso"], dict):
            raise ValueError("'progresso' precisa ser um objeto")

        data = deepcopy(raw)
        data.setdefault("schema_version", SCHEMA_VERSION)
        data["schema_version"] = SCHEMA_VERSION
        return cls(data)

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.data)

    def to_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))


    def update_progress(self, *, current_location: str | None = None,
                        discovered_location: str | None = None,
                        visited_location: str | None = None,
                        event: dict[str, Any] | None = None) -> "AdventureState":
        """Aplica mudanças pequenas e determinísticas ao estado da aventura."""
        data = self.to_dict()
        progress = data["progresso"]
        if current_location is not None:
            progress["local_atual"] = current_location
        if discovered_location:
            discovered = progress.setdefault("locais_descobertos", [])
            if discovered_location not in discovered:
                discovered.append(discovered_location)
            for location in data["locais"]:
                if location.get("id") == discovered_location:
                    location["descoberto"] = True
                    break
        if visited_location:
            visited = progress.setdefault("locais_visitados", [])
            if visited_location not in visited:
                visited.append(visited_location)
            for location in data["locais"]:
                if location.get("id") == visited_location:
                    location["visitado"] = True
                    break
        if event:
            progress.setdefault("eventos_importantes", []).append(deepcopy(event))
        return AdventureState.from_dict(data)

    def reveal_secret(self, secret_id: str) -> "AdventureState":
        data = self.to_dict()
        for secret in data.get("segredos", []):
            if secret.get("id") == secret_id:
                secret["revelado"] = True
                break
        return AdventureState.from_dict(data)

    def complete_encounter(self, encounter_id: str) -> "AdventureState":
        data = self.to_dict()
        for encounter in data.get("encounters", []):
            if encounter.get("id") == encounter_id:
                encounter["status"] = "concluido"
                break
        completed = data["progresso"].setdefault("encounters_concluidos", [])
        if encounter_id not in completed:
            completed.append(encounter_id)
        return AdventureState.from_dict(data)

    def complete_quest_step(self, quest_id: str, step_id: str) -> "AdventureState":
        data = self.to_dict()
        for quest in data.get("quests", []):
            if quest.get("id") != quest_id:
                continue
            for step in quest.get("etapas", []):
                if step.get("id") == step_id:
                    step["status"] = "concluida"
            if quest.get("etapas") and all(step.get("status") == "concluida" for step in quest["etapas"]):
                quest["status"] = "concluida"
                completed = data["progresso"].setdefault("quests_concluidas", [])
                if quest_id not in completed:
                    completed.append(quest_id)
        return AdventureState.from_dict(data)


def empty_adventure_state(
    *,
    titulo: str,
    resumo: str,
    local_inicial: str,
    narrativa_inicial: str,
) -> dict[str, Any]:
    """Cria um estado mínimo quando nenhum provedor de IA está disponível."""

    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in titulo).strip("_")
    return {
        "schema_version": SCHEMA_VERSION,
        "aventura": {
            "id": slug or "aventura",
            "titulo": titulo,
            "resumo": resumo,
            "sistema": "D&D 5e 2014",
            "status": "em_andamento",
        },
        "mundo": {
            "regiao": "desconhecida",
            "cidade": {
                "nome": "desconhecida",
                "descricao": "",
            },
        },
        "locais": [
            {
                "id": "local_inicial",
                "nome": local_inicial,
                "tipo": "inicio",
                "descricao": narrativa_inicial,
                "descoberto": True,
                "visitado": True,
                "conexoes": [],
            }
        ],
        "npcs": [],
        "encounters": [],
        "quests": [],
        "itens": [],
        "flags": {},
        "segredos": [],
        "progresso": {
            "local_atual": "local_inicial",
            "locais_descobertos": ["local_inicial"],
            "locais_visitados": ["local_inicial"],
            "npcs_conhecidos": [],
            "encounters_concluidos": [],
            "quests_concluidas": [],
            "eventos_importantes": [],
        },
    }


def adventure_generation_prompt() -> str:
    """Contrato estável para a geração inicial, sem engessar o conteúdo."""

    return """
Crie uma aventura NOVA de D&D 5e 2014. Não reutilize uma aventura pré-escrita.
Você tem liberdade criativa para escolher tema, cidade, locais, NPCs, inimigos,
segredos, objetivos e reviravoltas. O formato abaixo é obrigatório, mas o
conteúdo deve ser regenerado a cada nova aventura.

Retorne SOMENTE JSON válido, sem markdown.

{
  "schema_version": 1,
  "aventura": {
    "id": "slug-curto",
    "titulo": "...",
    "resumo": "...",
    "sistema": "D&D 5e 2014",
    "status": "em_andamento"
  },
  "mundo": {
    "regiao": "...",
    "cidade": {"nome": "...", "descricao": "..."}
  },
  "locais": [
    {
      "id": "id_unico",
      "nome": "...",
      "tipo": "cidade|taverna|estrada|dungeon|encontro|boss|outro",
      "descricao": "...",
      "descoberto": true,
      "visitado": false,
      "conexoes": ["outro_id"],
      "encontros": ["encounter_id"]
    }
  ],
  "npcs": [
    {
      "id": "id_unico",
      "nome": "...",
      "funcao": "...",
      "local_atual": "local_id",
      "descricao": "...",
      "motivacao": "...",
      "informacoes": ["..."],
      "segredos": ["secret_id"],
      "vivo": true
    }
  ],
  "encounters": [
    {
      "id": "id_unico",
      "local": "local_id",
      "tipo": "combate|social|armadilha|investigacao|outro",
      "status": "pendente",
      "descricao": "...",
      "inimigos": []
    }
  ],
  "quests": [
    {
      "id": "id_unico",
      "titulo": "...",
      "tipo": "principal|secundaria",
      "status": "ativa",
      "objetivo": "...",
      "etapas": [
        {"id": "id", "descricao": "...", "status": "pendente"}
      ]
    }
  ],
  "itens": [
    {
      "id": "id_unico",
      "nome": "...",
      "tipo": "quest|magico|comum",
      "local_atual": "local_id",
      "portador": null,
      "importante": true
    }
  ],
  "flags": {},
  "segredos": [
    {
      "id": "id_unico",
      "descricao": "...",
      "revelado": false
    }
  ],
  "progresso": {
    "local_atual": "id_do_local_inicial",
    "locais_descobertos": ["id_do_local_inicial"],
    "locais_visitados": [],
    "npcs_conhecidos": [],
    "encounters_concluidos": [],
    "quests_concluidas": [],
    "eventos_importantes": []
  },
  "narrativa_inicial": "Texto curto para apresentar a aventura ao grupo."
}

Regras de geração:
- Crie pelo menos 4 locais além do local inicial quando fizer sentido.
- Inclua pelo menos 2 NPCs relevantes.
- Inclua pelo menos 1 objetivo principal e 1 possível objetivo secundário.
- Inclua encontros potenciais, mas NÃO force todos a acontecerem.
- Inclua pelo menos 1 segredo ou informação que possa ser descoberta.
- Faça conexões coerentes entre os locais.
- Não escreva uma aventura linear completa. Crie possibilidades e estado inicial.
- O Game Engine decidirá testes, combate, movimento e consequências mecânicas.
- A IA será responsável pela criatividade e pela narrativa, não por inventar
  resultados mecânicos fora do estado.
""".strip()
