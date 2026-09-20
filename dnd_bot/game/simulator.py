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

from .action import ActionResolver, normalize
from .adventure import AdventureState
from .character import Character
from .combat import CombatState, Combatant, combatant_from_character
from .engine import GameEngine
from .director import SceneDirector
from .party import PartyDecision, PartyDecisionResolver, PartyVote
from .participation import PartyParticipation, PartyParticipationResolver
from .validator import AdventureValidator


class PlayerAgent(Protocol):
    """Contrato para qualquer agente que possa controlar um personagem."""

    def choose_action(self, state: AdventureState, character: Character, step: int) -> str:
        ...

    def choose_vote(
        self,
        decision: PartyDecision,
        state: AdventureState,
        character: Character,
        step: int,
    ) -> str:
        """Escolhe uma opção quando a party entra em votação."""
        ...

    def choose_participation(
        self,
        selected_option: str,
        state: AdventureState,
        character: Character,
        step: int,
    ) -> bool:
        """Decide se o personagem participa da ação aprovada."""
        ...


@dataclass(frozen=True)
class GoalDrivenPlayerAgent:
    """Agente determinístico que tenta progredir usando o estado da campanha."""

    def choose_action(self, state: AdventureState, character: Character, step: int) -> str:
        current_id = state.data.get("progresso", {}).get("local_atual")
        current = next(
            (loc for loc in state.data.get("locais", []) if loc.get("id") == current_id),
            None,
        )
        if current:
            for connection in current.get("conexoes", []):
                location = next(
                    (loc for loc in state.data.get("locais", []) if loc.get("id") == connection),
                    None,
                )
                if location and location.get("descoberto"):
                    return f"ir para {location.get('nome')}"
        return "investigar a área"


@dataclass(frozen=True)
class PartyMember:
    """Jogador simulado e seu personagem dentro de uma party."""
    character: Character
    agent: PlayerAgent
    player_id: str | None = None


@dataclass
class PartySimulationResult:
    """Resultado de uma simulação multiparticipante."""
    state: AdventureState
    report: SimulationReport
    rounds: int = 0
    decisions: int = 0
    members: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PersonalityPlayerAgent:
    """Agente determinístico com um perfil simples de decisão."""
    personality: str

    def choose_participation(
        self,
        selected_option: str,
        state: AdventureState,
        character: Character,
        step: int,
    ) -> bool:
        return self.personality != "cauteloso" or "atacar" not in selected_option.lower()

    def choose_vote(
        self,
        decision: PartyDecision,
        state: AdventureState,
        character: Character,
        step: int,
    ) -> str:
        options = decision.options
        lower = {option.lower(): option for option in options}

        if self.personality == "social":
            for option in options:
                if any(word in option.lower() for word in ("conversar", "falar", "negociar")):
                    return option
        if self.personality == "cauteloso":
            for option in options:
                if any(word in option.lower() for word in ("observar", "investigar")):
                    return option
        if self.personality == "agressivo":
            for option in options:
                if any(word in option.lower() for word in ("atacar", "combater")):
                    return option
        return options[0]

    def choose_action(self, state: AdventureState, character: Character, step: int) -> str:
        current_id = state.data.get("progresso", {}).get("local_atual")
        current = next((loc for loc in state.data.get("locais", []) if loc.get("id") == current_id), None)
        if self.personality == "social":
            npcs = [npc for npc in state.data.get("npcs", []) if npc.get("local_atual") == current_id and npc.get("vivo", True)]
            if npcs:
                return f"falar com {npcs[0].get('nome')}"
        if self.personality == "cauteloso":
            return "observar o ambiente"
        if self.personality == "agressivo":
            encounters = [e for e in state.data.get("encounters", []) if e.get("local") == current_id and e.get("status") == "pendente"]
            if encounters:
                return "atacar o inimigo"
        if current:
            for connection in current.get("conexoes", []):
                location = next((loc for loc in state.data.get("locais", []) if loc.get("id") == connection), None)
                if location and location.get("descoberto"):
                    return f"ir para {location.get('nome')}"
        return "investigar a área"


class ScriptedPlayerAgent:
    """Agente previsível para testes de regressão."""

    def choose_participation(
        self,
        selected_option: str,
        state: AdventureState,
        character: Character,
        step: int,
    ) -> bool:
        return True

    def choose_vote(
        self,
        decision: PartyDecision,
        state: AdventureState,
        character: Character,
        step: int,
    ) -> str:
        return decision.options[0]

    actions: tuple[str, ...] = (
        "investigar a taverna",
        "entrar no Beco da Cinza",
        "investigar o beco",
        "entrar na Cripta de Valdrak",
        "observar o ambiente",
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
    director_levels: list[str] = field(default_factory=list)
    suggestions_presented: int = 0
    loops_detected: int = 0
    decision_rounds: int = 0
    votes: int = 0
    decisions_accepted: int = 0
    decisions_rejected: int = 0
    participation_rounds: int = 0
    participants: int = 0
    declined_participation: int = 0
    individual_results: int = 0
    action_history: list[str] = field(default_factory=list)

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
        self.director = SceneDirector()
        self.validator = AdventureValidator()

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
            self.validator.assert_valid(state)
            report.events.append("campanha_validada")

            for step in range(max_steps):
                if self._quest_completed(state):
                    break

                action = agent.choose_action(state, character, step)
                if not isinstance(action, str) or not action.strip():
                    raise ValueError("PlayerAgent retornou uma ação vazia.")

                idle_steps = self._idle_steps(report)
                suggestion = self.director.evaluate(
                    state,
                    recent_steps=idle_steps,
                    progress_since_last_scene=not self._has_been_idle(report),
                )
                report.director_levels.append(suggestion.level)
                if suggestion.level in {"suggestion", "intervention"}:
                    report.suggestions_presented += 1

                normalized_action = normalize(action)
                if self._is_repeated_action(report.action_history, normalized_action):
                    report.loops_detected += 1
                    if report.loops_detected >= 3:
                        raise RuntimeError("Loop de ações detectado no simulador.")

                before = self._state_signature(state)
                report.action_history.append(normalized_action)
                report.steps += 1
                state = self._resolve_action(state, character, action, report)
                self.validator.assert_valid(state)

                if include_combat:
                    state = self._run_pending_encounters(state, character, report)
                    self.validator.assert_valid(state)

                after = self._state_signature(state)
                report.events.append("sem_progresso" if before == after else "progresso")

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

    def run_party(
        self,
        adventure: AdventureState,
        members: list[PartyMember],
        *,
        max_rounds: int = 20,
        include_combat: bool = True,
    ) -> PartySimulationResult:
        """Simula decisões de vários jogadores sobre o mesmo estado da campanha."""
        if not members:
            raise ValueError("A party precisa ter pelo menos um membro.")
        if max_rounds < 1:
            raise ValueError("max_rounds deve ser positivo.")

        state = adventure
        report = SimulationReport(status="em_andamento")
        decisions = 0
        rounds = 0
        try:
            self._validate_initial_state(state)
            self.validator.assert_valid(state)
            report.events.append("campanha_validada")
            for _round in range(max_rounds):
                if self._quest_completed(state):
                    break
                rounds += 1
                suggestion = self.director.evaluate(
                    state,
                    recent_steps=self._idle_steps(report),
                    progress_since_last_scene=not self._has_been_idle(report),
                )
                report.director_levels.append(suggestion.level)
                if suggestion.level in {"suggestion", "intervention"}:
                    report.suggestions_presented += 1

                resolution = None
                if suggestion.level in {"suggestion", "intervention"}:
                    resolution = self._party_decision(
                        suggestion,
                        state,
                        members,
                        decisions,
                        report,
                    )

                if resolution is not None and resolution.accepted:
                    selected = str(resolution.selected_option)
                    participation = self._party_participation(
                        resolution.decision_id,
                        selected,
                        state,
                        members,
                        decisions,
                        report,
                    )
                    if participation.participants:
                        for item in participation.participants:
                            member = next(
                                m for m in members
                                if (m.player_id or m.character.name) == item.player_id
                            )
                            action = item.action
                            normalized = normalize(action)
                            if self._is_repeated_action(report.action_history, normalized):
                                report.loops_detected += 1
                                if report.loops_detected >= 3:
                                    raise RuntimeError("Loop de ações detectado na party.")
                            before = self._state_signature(state)
                            report.action_history.append(normalized)
                            report.steps += 1
                            decisions += 1
                            report.events.append(
                                f"participante:{member.character.name}:acao:{normalized}"
                            )
                            state = self._resolve_action(
                                state,
                                member.character,
                                action,
                                report,
                            )
                            report.individual_results += 1
                            if include_combat:
                                state = self._run_pending_encounters(
                                    state,
                                    member.character,
                                    report,
                                )
                            after = self._state_signature(state)
                            report.events.append(
                                "sem_progresso" if before == after else "progresso"
                            )
                    continue

                for member in members:
                    if self._quest_completed(state):
                        break
                    action = member.agent.choose_action(state, member.character, decisions)
                    if not isinstance(action, str) or not action.strip():
                        raise ValueError(f"PlayerAgent inválido para {member.character.name}.")
                    normalized = normalize(action)
                    if self._is_repeated_action(report.action_history, normalized):
                        report.loops_detected += 1
                        if report.loops_detected >= 3:
                            raise RuntimeError("Loop de ações detectado na party.")
                    idle_steps = self._idle_steps(report)
                    suggestion = self.director.evaluate(
                        state,
                        recent_steps=idle_steps,
                        progress_since_last_scene=not self._has_been_idle(report),
                    )
                    report.director_levels.append(suggestion.level)
                    if suggestion.level in {"suggestion", "intervention"}:
                        report.suggestions_presented += 1
                    before = self._state_signature(state)
                    report.action_history.append(normalized)
                    report.steps += 1
                    decisions += 1
                    report.events.append(f"jogador:{member.character.name}:acao:{normalized}")
                    state = self._resolve_action(state, member.character, action, report)
                    if include_combat:
                        state = self._run_pending_encounters(state, member.character, report)
                    after = self._state_signature(state)
                    report.events.append("sem_progresso" if before == after else "progresso")
            if self._quest_completed(state):
                report.quests_completed = len(state.data["progresso"].get("quests_concluidas", []))
                report.status = "concluida"
            else:
                report.status = "sem_desfecho"
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            report.status = "falhou"
            report.failures.append(str(exc))
        report.locations_discovered = len(state.data["progresso"].get("locais_descobertos", []))
        return PartySimulationResult(
            state=state,
            report=report,
            rounds=rounds,
            decisions=decisions,
            members=[m.character.name for m in members],
        )

    def _party_participation(
        self,
        decision_id: str,
        selected_option: str,
        state: AdventureState,
        members: list[PartyMember],
        step: int,
        report: SimulationReport,
    ):
        report.participation_rounds += 1
        items = []
        for member in members:
            chooser = getattr(member.agent, "choose_participation", None)
            participates = (
                bool(chooser(selected_option, state, member.character, step))
                if callable(chooser)
                else True
            )
            items.append(
                PartyParticipation(
                    player_id=member.player_id or member.character.name,
                    action=selected_option,
                    participate=participates,
                )
            )

        resolution = PartyParticipationResolver().resolve(
            decision_id,
            selected_option,
            items,
        )
        report.participants += len(resolution.participants)
        report.declined_participation += len(resolution.declined)
        for participant in resolution.participants:
            report.events.append(
                f"participacao:{participant.player_id}:aceita:{normalize(participant.action)}"
            )
        for player_id in resolution.declined:
            report.events.append(f"participacao:{player_id}:recusa")
        return resolution

    def _party_decision(
        self,
        suggestion,
        state: AdventureState,
        members: list[PartyMember],
        step: int,
        report: SimulationReport,
    ):
        """Converte uma sugestão do Director em Decision -> Vote -> Resolution."""
        if not suggestion.actions:
            return None

        decision = PartyDecision(
            id=f"scene-{report.decision_rounds + 1}",
            prompt="A party quer seguir uma destas oportunidades?",
            options=tuple(suggestion.actions),
            reason=suggestion.reason,
        )
        report.decision_rounds += 1

        votes = []
        for member in members:
            chooser = getattr(member.agent, "choose_vote", None)
            option = (
                chooser(decision, state, member.character, step)
                if callable(chooser)
                else decision.options[0]
            )
            votes.append(
                PartyVote(
                    voter_id=member.player_id or member.character.name,
                    option=option,
                )
            )
        report.votes += len(votes)

        resolution = PartyDecisionResolver().resolve(decision, votes)
        report.events.append(
            f"decisao:{decision.id}:"
            f"{'aceita' if resolution.accepted else 'rejeitada'}:"
            f"{resolution.selected_option or 'nenhuma'}"
        )
        if resolution.accepted:
            report.decisions_accepted += 1
        else:
            report.decisions_rejected += 1
        return resolution

    def _is_repeated_action(self, history: list[str], action: str) -> bool:
        return len(history) >= 2 and history[-1] == action and history[-2] == action

    def _idle_steps(self, report: SimulationReport) -> int:
        idle = 0
        for event in reversed(report.events):
            if event == "sem_progresso":
                idle += 1
            elif event == "progresso":
                break
        return idle

    def _has_been_idle(self, report: SimulationReport) -> bool:
        return self._idle_steps(report) > 0

    def _state_signature(self, state: AdventureState) -> str:
        return state.to_json()

    def _quest_completed(self, state: AdventureState) -> bool:
        return any(
            quest.get("status") == "concluida"
            for quest in state.data.get("quests", [])
        )

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
                state = self._discover_next_location(state, character.name, report)

        if intent.tipo == "movimento" and intent.destino:
            state = self._move_character(state, intent.destino, character.name, report)

        report.events.append(f"acao:{intent.tipo}")
        return state

    def _move_character(
        self,
        state: AdventureState,
        destination: str,
        character_name: str,
        report: SimulationReport,
    ) -> AdventureState:
        progress = state.data["progresso"]
        current_id = progress.get("local_atual")
        current = next(
            (loc for loc in state.data["locais"] if loc.get("id") == current_id),
            None,
        )
        target = next(
            (loc for loc in state.data["locais"] if loc.get("id") == destination),
            None,
        )
        if not current or not target:
            raise ValueError("Movimento referencia local inexistente.")

        if destination != current_id and destination not in current.get("conexoes", []):
            raise ValueError(f"Destino inacessível: {destination}")

        state = self.engine.apply_action_event(
            state,
            event_type="movimento",
            description=f"{character_name} foi para {target.get('nome')}.",
            current_location=destination,
            discovered_location=destination,
            visited_location=destination,
        )

        state = self._complete_matching_quest_step(
            state,
            target_type="local",
            target_id=destination,
        )

        report.events.append(f"movimento:{destination}")
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

    def _run_pending_encounters(
        self,
        state: AdventureState,
        character: Character,
        report: SimulationReport,
    ) -> AdventureState:
        """Dispara apenas encontros de combate pendentes no local atual."""
        current_id = state.data["progresso"].get("local_atual")
        encounters = [
            encounter for encounter in state.data.get("encounters", [])
            if encounter.get("local") == current_id
            and encounter.get("status") == "pendente"
            and encounter.get("tipo") == "combate"
        ]
        for encounter in encounters:
            state = self._run_combat(
                state,
                character,
                report,
                encounter_id=encounter["id"],
                enemy_name=(encounter.get("inimigos") or ["Inimigo"])[0],
            )
        return state

    def _run_combat(
        self,
        state: AdventureState,
        character: Character,
        report: SimulationReport,
        *,
        encounter_id: str = "encontro_guardiao",
        enemy_name: str = "Guarda da Cripta",
    ) -> AdventureState:
        enemy = Combatant(
            name=enemy_name,
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
        state = self.engine.apply_action_event(
            state,
            event_type="combate",
            description="O encontro de teste foi concluído.",
        )
        state = state.complete_encounter(encounter_id)
        state = self._complete_matching_quest_step(
            state,
            target_type="encounter",
            target_id=encounter_id,
        )
        return state

    def _complete_matching_quest_step(
        self,
        state: AdventureState,
        *,
        target_type: str,
        target_id: str,
    ) -> AdventureState:
        """Conclui a primeira etapa pendente cujo alvo foi realmente alcançado."""
        for quest in state.data.get("quests", []):
            if quest.get("status") == "concluida":
                continue
            for step in quest.get("etapas", []):
                if step.get("status") == "concluida":
                    continue
                target = step.get("alvo") or {}
                if target.get("tipo") == target_type and target.get("id") == target_id:
                    return state.complete_quest_step(
                        quest.get("id"),
                        step.get("id"),
                    )
                if target_type == "local" and step.get("local_objetivo") == target_id:
                    return state.complete_quest_step(
                        quest.get("id"),
                        step.get("id"),
                    )
                break
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
                            "alvo": {"tipo": "local", "id": "beco"},
                        },
                        {
                            "id": "entrar_cripta",
                            "descricao": "Chegar à Cripta de Valdrak.",
                            "status": "pendente",
                            "alvo": {"tipo": "local", "id": "cripta"},
                        },
                        {
                            "id": "derrotar_guardiao",
                            "descricao": "Superar o guardião.",
                            "status": "pendente",
                            "alvo": {"tipo": "encounter", "id": "encontro_guardiao"},
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
    "GoalDrivenPlayerAgent",
    "PartyMember",
    "PartySimulationResult",
    "PersonalityPlayerAgent",
]


def main() -> int:
    """Executa o vertical slice manualmente: python -m dnd_bot.game.simulator."""
    import json

    character = Character(
        name="Simulador",
        race="Humano",
        class_name="Guerreiro",
        abilities={
            "Força": 16,
            "Destreza": 12,
            "Constituição": 14,
            "Inteligência": 14,
            "Sabedoria": 12,
            "Carisma": 10,
        },
        level=1,
        max_hp=20,
        hp=20,
        armor_class=15,
    )
    result = CampaignSimulator(rng=_CliRng()).run(
        build_vertical_slice_adventure(),
        character,
        max_steps=10,
    )
    print(json.dumps({
        "status": result.report.status,
        "passed": result.report.passed,
        "steps": result.report.steps,
        "checks": result.report.checks,
        "successful_checks": result.report.successful_checks,
        "failed_checks": result.report.failed_checks,
        "combats": result.report.combats,
        "combat_rounds": result.report.combat_rounds,
        "quests_completed": result.report.quests_completed,
        "locations_discovered": result.report.locations_discovered,
        "events": result.report.events,
        "failures": result.report.failures,
    }, ensure_ascii=False, indent=2))
    return 0 if result.report.passed else 1


class _CliRng:
    def randint(self, low: int, high: int) -> int:
        return 10 if high == 20 else 4


if __name__ == "__main__":
    raise SystemExit(main())
