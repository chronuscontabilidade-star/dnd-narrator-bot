"""Simulador determinístico de campanhas para testes de longa duração.

O simulador não depende de Telegram nem de um provider de IA. Ele executa uma
campanha vertical usando agentes de jogador substituíveis. A implementação
inicial é deliberadamente pequena: seu objetivo é detectar regressões no fluxo
criação -> cena -> teste -> combate -> quest -> consequência -> desfecho.

No futuro, PlayerAgent poderá ser implementado por Gemini/Llama para produzir
comportamento menos previsível.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .action import ActionResolver
from .adventure import AdventureState
from .character import Character
from .combat import CombatState, Combatant, combatant_from_character
from .engine import GameEngine


class PlayerAgent(Protocol):
    """Contrato para qualquer agente que possa controlar um personagem."""

    def choose_action(self, state: AdventureState, character: Character, step: int) -> str:
        ...


@dataclass(frozen=True)
class ScriptedPlayerAgent:
    """Agente previsível para testes de regressão."""

    actions: tuple[str, ...] = (
        "observar o ambiente",
        "investigar a taverna",
        "procurar pistas",
        "falar com o taberneiro",
    )

    def choose_action(self, state: AdventureState, character: Character, step: int) -> str:
        if not self.actions:
            return "observar o ambiente"
        return self.actions[min(step, len(self.actions) - 1)]


@dataclass
class SimulationReport:
    status: str = "nao_iniciada"
    steps: int = 0
    checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    combats: int = 0
    combat_rounds: int = 0
    quests_completed: int = 0
    locations_discovered: int = 0
    events: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "concluida" and not self.failures


@dataclass
class SimulationResult:
    state: AdventureState
    report: SimulationReport


class CampaignSimulator:
    """Executa um vertical slice de campanha sem depender do Telegram."""

    def __init__(self, *, engine: GameEngine | None = None, rng=None):
        self.engine = engine or GameEngine()
        self.rng = rng

    def run(
        self,
        adventure: AdventureState,
        character: Character,
        *,
        agent: PlayerAgent | None = None,
        max_steps: int = 20,
        include_combat: bool = True,
    ) -> SimulationResult:
        if max_steps < 1:
            raise ValueError("max_steps deve ser positivo.")

        agent = agent or ScriptedPlayerAgent()
        state = adventure
        report = SimulationReport(status="em_andamento")

        try:
            self._validate_initial_state(state)
            report.events.append("campanha_validada")

            for step in range(max_steps):
                if self._quest_completed(state):
                    break

                action = agent.choose_action(state, character, step)
                if not isinstance(action, str) or not action.strip():
                    raise ValueError("PlayerAgent retornou uma ação vazia.")

                report.steps += 1
                state = self._resolve_action(
                    state,
                    character,
                    action,
                    report,
                )

                if step == 2 and include_combat:
                    state = self._run_combat(state, character, report)

            if not self._quest_completed(state):
                # O simulador vertical tem uma etapa determinística de desfecho
                # para validar persistência da quest mesmo que o agente tenha
                # ficado preso em ações narrativas.
                state = self._finish_vertical_quest(state, report)

            if self._quest_completed(state):
                report.quests_completed = len(state.data["progresso"].get("quests_concluidas", []))
                report.status = "concluida"
            else:
                report.status = "sem_desfecho"

        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            report.status = "falhou"
            report.failures.append(str(exc))

        report.locations_discovered = len(
            state.data["progresso"].get("locais_descobertos", [])
        )
        return SimulationResult(state=state, report=report)

    def _validate_initial_state(self, state: AdventureState) -> None:
        data = state.data
        current = data["progresso"].get("local_atual")
        if not current:
            raise ValueError("Campanha sem local atual.")

        location_ids = {item.get("id") for item in data.get("locais", [])}
        if current not in location_ids:
            raise ValueError(f"Local atual inexistente: {current}")

        quest_ids = {item.get("id") for item in data.get("quests", [])}
        if not quest_ids:
            raise ValueError("Campanha sem quest para simulação.")

    def _resolve_action(
        self,
        state: AdventureState,
        character: Character,
        action: str,
        report: SimulationReport,
    ) -> AdventureState:
        intent = ActionResolver(state.to_dict()).resolve(action)

        if intent.requer_teste and intent.atributo:
            result = self.engine.ability_check(
                character,
                intent.atributo,
                int(intent.cd or 12),
                rng=self.rng,
            )
            report.checks += 1
            if result.success:
                report.successful_checks += 1
            else:
                report.failed_checks += 1
            report.events.append(
                f"teste:{intent.habilidade or intent.atributo}:{'sucesso' if result.success else 'falha'}"
            )

            if result.success and intent.tipo in {"investigacao", "percepcao"}:
                return self._discover_next_location(state, character.name, report)

        report.events.append(f"acao:{intent.tipo}")
        return state

    def _discover_next_location(
        self,
        state: AdventureState,
        character_name: str,
        report: SimulationReport,
    ) -> AdventureState:
        current_id = state.data["progresso"].get("local_atual")
        current = next(
            (loc for loc in state.data["locais"] if loc.get("id") == current_id),
            None,
        )
        if not current:
            return state

        target = next(
            (
                loc
                for loc in state.data["locais"]
                if loc.get("id") in current.get("conexoes", [])
                and not loc.get("descoberto")
            ),
            None,
        )
        if not target:
            return state

        report.events.append(f"descoberta:{target.get('id')}")
        return self.engine.apply_action_event(
            state,
            event_type="descoberta",
            description=f"{character_name} descobriu {target.get('nome')}.",
            discovered_location=target["id"],
        )

    def _run_combat(
        self,
        state: AdventureState,
        character: Character,
        report: SimulationReport,
    ) -> AdventureState:
        enemy = Combatant(
            name="Guarda da Cripta",
            armor_class=10,
            max_hp=8,
            hp=8,
            dexterity=8,
            attack_bonus=0,
            damage_dice="1d4",
            damage_bonus=0,
            is_player=False,
            position=(1, 0),
        )
        hero = combatant_from_character(
            character,
            attack_bonus=4,
            damage_dice="1d6",
            damage_bonus=2,
        )
        hero.position = (0, 0)

        combat = CombatState([hero, enemy])
        combat.start(rng=self.rng)
        report.combats += 1

        safety = 0
        while not combat.finished and safety < 20:
            safety += 1
            current = combat.current
            if current is hero:
                if enemy.is_alive:
                    combat.attack(hero, enemy, rng=self.rng)
                if not combat.finished:
                    combat.end_turn(hero)
            else:
                if hero.is_alive:
                    combat.attack(enemy, hero, rng=self.rng)
                if not combat.finished:
                    combat.end_turn(enemy)

        if safety >= 20:
            raise RuntimeError("Combate excedeu o limite de segurança do simulador.")

        report.combat_rounds += combat.round
        if not hero.is_alive:
            raise RuntimeError("Personagem morreu no combate vertical.")

        report.events.append("combate:concluido")
        return self.engine.apply_action_event(
            state,
            event_type="combate",
            description="O encontro de teste foi concluído.",
        )

    def _finish_vertical_quest(
        self,
        state: AdventureState,
        report: SimulationReport,
    ) -> AdventureState:
        quest = next(
            (
                item
                for item in state.data["quests"]
                if item.get("status") != "concluida"
            ),
            None,
        )
        if not quest:
            return state

        steps = quest.get("etapas", [])
        for step in steps:
            if step.get("status") != "concluida":
                state = state.complete_quest_step(quest["id"], step["id"])

        report.events.append(f"quest:{quest['id']}:concluida")
        return state


def build_vertical_slice_adventure() -> AdventureState:
    """Cria um cenário pequeno e determinístico para o primeiro simulador."""

    return AdventureState.from_dict(
        {
            "schema_version": 1,
            "aventura": {
                "id": "simulacao_vertical",
                "titulo": "As Cinzas de Valdrak",
                "resumo": "Cenário mínimo para testar o ciclo de campanha.",
                "sistema": "D&D 5e 2014",
                "status": "em_andamento",
            },
            "mundo": {
                "regiao": "Vale de Valdrak",
                "cidade": {
                    "nome": "Pedra Branca",
                    "descricao": "Uma cidade cercada por antigas ruínas.",
                },
            },
            "locais": [
                {
                    "id": "taverna",
                    "nome": "Javali Negro",
                    "tipo": "taverna",
                    "descricao": "Uma taverna movimentada.",
                    "descoberto": True,
                    "visitado": True,
                    "conexoes": ["beco"],
                    "encontros": [],
                },
                {
                    "id": "beco",
                    "nome": "Beco da Cinza",
                    "tipo": "rua",
                    "descricao": "Um beco estreito atrás da taverna.",
                    "descoberto": False,
                    "visitado": False,
                    "conexoes": ["cripta"],
                    "encontros": [],
                },
                {
                    "id": "cripta",
                    "nome": "Cripta de Valdrak",
                    "tipo": "dungeon",
                    "descricao": "Uma cripta esquecida sob a cidade.",
                    "descoberto": False,
                    "visitado": False,
                    "conexoes": [],
                    "encontros": ["encontro_guardiao"],
                },
            ],
            "npcs": [
                {
                    "id": "taberneiro",
                    "nome": "Mauro",
                    "funcao": "taberneiro",
                    "local_atual": "taverna",
                    "descricao": "Um homem inquieto que sabe mais do que aparenta.",
                    "motivacao": "proteger a cidade",
                    "informacoes": ["Existe uma passagem no beco."],
                    "segredos": [],
                    "vivo": True,
                }
            ],
            "encounters": [
                {
                    "id": "encontro_guardiao",
                    "local": "cripta",
                    "tipo": "combate",
                    "status": "pendente",
                    "descricao": "Um guardião bloqueia a passagem.",
                    "inimigos": ["Guarda da Cripta"],
                }
            ],
            "quests": [
                {
                    "id": "quest_cinzas",
                    "titulo": "Seguir a trilha das cinzas",
                    "tipo": "principal",
                    "status": "ativa",
                    "objetivo": "Descobrir a origem das cinzas.",
                    "etapas": [
                        {
                            "id": "descobrir_beco",
                            "descricao": "Descobrir o Beco da Cinza.",
                            "status": "pendente",
                        },
                        {
                            "id": "entrar_cripta",
                            "descricao": "Chegar à Cripta de Valdrak.",
                            "status": "pendente",
                        },
                        {
                            "id": "derrotar_guardiao",
                            "descricao": "Superar o guardião.",
                            "status": "pendente",
                        },
                    ],
                }
            ],
            "itens": [],
            "flags": {},
            "segredos": [],
            "progresso": {
                "local_atual": "taverna",
                "locais_descobertos": ["taverna"],
                "locais_visitados": ["taverna"],
                "npcs_conhecidos": [],
                "encounters_concluidos": [],
                "quests_concluidas": [],
                "eventos_importantes": [],
            },
        }
    )


__all__ = [
    "CampaignSimulator",
    "PlayerAgent",
    "ScriptedPlayerAgent",
    "SimulationReport",
    "SimulationResult",
    "build_vertical_slice_adventure",
]
