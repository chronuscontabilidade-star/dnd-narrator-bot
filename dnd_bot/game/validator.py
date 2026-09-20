"""Validação estrutural e semântica básica do estado de uma campanha."""

from __future__ import annotations

from dataclasses import dataclass

from .adventure import AdventureState


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"


class AdventureValidator:
    """Detecta estados impossíveis e problemas de coerência verificáveis por código."""

    def validate(self, state: AdventureState) -> tuple[ValidationIssue, ...]:
        data = state.data
        issues: list[ValidationIssue] = []

        locations = data.get("locais", [])
        npcs = data.get("npcs", [])
        encounters = data.get("encounters", [])
        quests = data.get("quests", [])
        items = data.get("itens", [])
        secrets = data.get("segredos", [])
        progress = data.get("progresso", {})

        location_ids = self._unique_ids(locations, "local", issues)
        npc_ids = self._unique_ids(npcs, "npc", issues)
        encounter_ids = self._unique_ids(encounters, "encounter", issues)
        quest_ids = self._unique_ids(quests, "quest", issues)
        item_ids = self._unique_ids(items, "item", issues)
        secret_ids = self._unique_ids(secrets, "segredo", issues)
        flags = data.get("flags", {})

        current = progress.get("local_atual")
        if current not in location_ids:
            issues.append(ValidationIssue("invalid_current_location", f"Local atual inexistente: {current}"))
        elif current not in set(progress.get("locais_descobertos", [])):
            issues.append(ValidationIssue(
                "current_location_not_discovered",
                f"Local atual não está descoberto: {current}",
            ))

        for key, code in (
            ("locais_descobertos", "broken_discovered_location"),
            ("locais_visitados", "broken_visited_location"),
        ):
            for location_id in progress.get(key, []):
                if location_id not in location_ids:
                    issues.append(ValidationIssue(code, f"{key} referencia local inexistente: {location_id}"))

        for location in locations:
            location_id = location.get("id")
            connections = location.get("conexoes", [])
            for connection in connections:
                if connection not in location_ids:
                    issues.append(ValidationIssue(
                        "broken_location_connection",
                        f"Local {location_id} referencia conexão inexistente: {connection}",
                    ))
            for encounter_id in location.get("encontros", []):
                if encounter_id not in encounter_ids:
                    issues.append(ValidationIssue(
                        "broken_location_encounter",
                        f"Local {location_id} referencia encounter inexistente: {encounter_id}",
                    ))

        # Coerência do grafo: locais de uma aventura gerada devem ser alcançáveis
        # a partir do início. Locais isolados são suspeitos, mas não impedem a
        # campanha, pois podem representar conteúdo secreto ou futuro.
        if current in location_ids:
            reachable = self._reachable_locations(locations, current)
            for location_id in location_ids - reachable:
                issues.append(ValidationIssue(
                    "unreachable_location",
                    f"Local {location_id} não é alcançável a partir de {current}.",
                    "warning",
                ))

        encounter_locations: dict[str, str] = {}
        for encounter in encounters:
            encounter_id = encounter.get("id")
            local_id = encounter.get("local")
            encounter_locations[encounter_id] = local_id
            if local_id not in location_ids:
                issues.append(ValidationIssue(
                    "broken_encounter_location",
                    f"Encounter {encounter_id} está em local inexistente: {local_id}",
                ))

        for location in locations:
            for encounter_id in location.get("encontros", []):
                if encounter_id in encounter_locations and encounter_locations[encounter_id] != location.get("id"):
                    issues.append(ValidationIssue(
                        "encounter_location_mismatch",
                        f"Encounter {encounter_id} está associado a {location.get('id')}, "
                        f"mas declara local {encounter_locations[encounter_id]}.",
                    ))

        for npc in npcs:
            npc_id = npc.get("id")
            if npc.get("local_atual") not in location_ids:
                issues.append(ValidationIssue(
                    "broken_npc_location",
                    f"NPC {npc_id} está em local inexistente: {npc.get('local_atual')}",
                ))
            for secret_id in npc.get("segredos", []):
                if secret_id not in secret_ids:
                    issues.append(ValidationIssue(
                        "broken_npc_secret",
                        f"NPC {npc_id} referencia segredo inexistente: {secret_id}",
                    ))

        for quest in quests:
            quest_id = quest.get("id")
            steps = quest.get("etapas", [])
            if not quest.get("titulo") or not quest.get("objetivo"):
                issues.append(ValidationIssue(
                    "incomplete_quest",
                    f"Quest {quest_id} não possui título ou objetivo.",
                ))
            if not steps:
                issues.append(ValidationIssue(
                    "quest_without_steps",
                    f"Quest {quest_id} não possui etapas executáveis.",
                ))

            step_ids: set[str] = set()
            for step in steps:
                step_id = step.get("id")
                target = step.get("local_objetivo")
                if target is not None and target not in location_ids:
                    issues.append(ValidationIssue(
                        "broken_quest_location",
                        f"Quest {quest_id}, etapa {step_id} referencia local inexistente: {target}",
                    ))
                if not step_id:
                    issues.append(ValidationIssue(
                        "missing_quest_step_id",
                        f"Quest {quest_id} possui etapa sem id.",
                    ))
                elif step_id in step_ids:
                    issues.append(ValidationIssue(
                        "duplicate_quest_step",
                        f"Quest {quest_id} possui etapa duplicada: {step_id}",
                    ))
                step_ids.add(step_id)

            statuses = {step.get("status") for step in steps}
            if steps and all(step.get("status") == "concluida" for step in steps):
                if quest.get("status") != "concluida":
                    issues.append(ValidationIssue(
                        "quest_status_inconsistent",
                        f"Quest {quest_id} tem todas as etapas concluídas, mas status={quest.get('status')}.",
                    ))
            if quest.get("status") == "concluida" and "concluida" not in statuses:
                issues.append(ValidationIssue(
                    "completed_quest_without_completed_steps",
                    f"Quest {quest_id} está concluída sem nenhuma etapa concluída.",
                ))

        for item in items:
            local_id = item.get("local_atual")
            if local_id is not None and local_id not in location_ids:
                issues.append(ValidationIssue(
                    "broken_item_location",
                    f"Item {item.get('id')} está em local inexistente: {local_id}",
                ))
            carrier = item.get("portador")
            if carrier is not None and carrier not in npc_ids:
                issues.append(ValidationIssue(
                    "broken_item_carrier",
                    f"Item {item.get('id')} referencia portador inexistente: {carrier}",
                ))

        reachable = (
            self._reachable_locations(locations, current)
            if current in location_ids
            else set()
        )
        encounter_locations = {
            encounter.get("id"): encounter.get("local")
            for encounter in encounters
            if encounter.get("id")
        }
        npc_locations = {
            npc.get("id"): npc.get("local_atual")
            for npc in npcs
            if npc.get("id")
        }
        item_locations = {
            item.get("id"): item.get("local_atual")
            for item in items
            if item.get("id")
        }

        for quest in quests:
            quest_id = quest.get("id")
            if quest.get("status") == "concluida":
                continue
            pending_steps = [
                step for step in quest.get("etapas", [])
                if step.get("status") != "concluida"
            ]
            if not pending_steps:
                issues.append(ValidationIssue(
                    "active_quest_without_pending_steps",
                    f"Quest {quest_id} não concluída não possui etapa pendente.",
                ))
                continue

            first_pending = pending_steps[0]
            target = first_pending.get("alvo")
            legacy_location = first_pending.get("local_objetivo")
            if target is None and legacy_location is not None:
                target = {"tipo": "local", "id": legacy_location}

            if target is None:
                issues.append(ValidationIssue(
                    "quest_step_without_structured_target",
                    f"Quest {quest_id}, etapa {first_pending.get('id')} não possui alvo estruturado.",
                    "warning",
                ))
                continue

            if not isinstance(target, dict):
                issues.append(ValidationIssue(
                    "invalid_quest_target",
                    f"Quest {quest_id}, etapa {first_pending.get('id')} possui alvo inválido.",
                ))
                continue

            target_type = target.get("tipo")
            target_id = target.get("id")
            target_sets = {
                "local": location_ids,
                "encounter": encounter_ids,
                "item": item_ids,
                "npc": npc_ids,
                "segredo": secret_ids,
            }
            if target_type == "flag":
                if not target_id or target_id not in flags:
                    issues.append(ValidationIssue(
                        "broken_quest_target",
                        f"Quest {quest_id}, etapa {first_pending.get('id')} referencia "
                        f"flag inexistente: {target_id}",
                    ))
                continue

            if target_type not in target_sets or target_id not in target_sets[target_type]:
                issues.append(ValidationIssue(
                    "broken_quest_target",
                    f"Quest {quest_id}, etapa {first_pending.get('id')} referencia "
                    f"{target_type} inexistente: {target_id}",
                ))
                continue

            target_location = None
            if target_type == "local":
                target_location = target_id
            elif target_type == "encounter":
                target_location = encounter_locations.get(target_id)
            elif target_type == "npc":
                target_location = npc_locations.get(target_id)
            elif target_type == "item":
                target_location = item_locations.get(target_id)
                if target_location is None:
                    carrier = next(
                        (item.get("portador") for item in items if item.get("id") == target_id),
                        None,
                    )
                    if carrier is not None:
                        target_location = npc_locations.get(carrier)

            if target_location is not None and target_location not in reachable:
                issues.append(ValidationIssue(
                    "quest_target_unreachable",
                    f"Quest {quest_id}, etapa {first_pending.get('id')} tem alvo "
                    f"inacessível a partir de {current}: {target_location}",
                ))

            if target_type == "encounter" and encounter_locations.get(target_id) is None:
                issues.append(ValidationIssue(
                    "quest_target_without_location",
                    f"Encounter objetivo {target_id} não possui local.",
                ))
            if target_type == "item" and target_location is None:
                issues.append(ValidationIssue(
                    "quest_item_without_acquisition_path",
                    f"Item objetivo {target_id} não possui local nem portador conhecido.",
                ))
            if target_type == "npc" and not npc_locations.get(target_id):
                issues.append(ValidationIssue(
                    "quest_npc_without_location",
                    f"NPC objetivo {target_id} não possui local atual.",
                ))

        for encounter_id in progress.get("encounters_concluidos", []):
            if encounter_id not in encounter_ids:
                issues.append(ValidationIssue(
                    "broken_completed_encounter",
                    f"Encounter concluído inexistente: {encounter_id}",
                ))

        for quest_id in progress.get("quests_concluidas", []):
            if quest_id not in quest_ids:
                issues.append(ValidationIssue(
                    "broken_completed_quest",
                    f"Quest concluída inexistente: {quest_id}",
                ))

        for secret_id in progress.get("segredos_revelados", []):
            if secret_id not in secret_ids:
                issues.append(ValidationIssue(
                    "broken_revealed_secret",
                    f"Segredo revelado inexistente: {secret_id}",
                ))

        return tuple(issues)

    def assert_valid(self, state: AdventureState) -> None:
        errors = [issue for issue in self.validate(state) if issue.severity == "error"]
        if errors:
            details = "; ".join(f"{issue.code}: {issue.message}" for issue in errors)
            raise ValueError(f"Estado de campanha inválido: {details}")

    @staticmethod
    def _reachable_locations(locations, start: str) -> set[str]:
        graph = {
            location.get("id"): set(location.get("conexoes", []))
            for location in locations
            if location.get("id")
        }
        reachable = {start}
        pending = [start]
        while pending:
            current = pending.pop()
            for target in graph.get(current, set()):
                if target in graph and target not in reachable:
                    reachable.add(target)
                    pending.append(target)
        return reachable

    @staticmethod
    def _unique_ids(items, kind: str, issues: list[ValidationIssue]) -> set[str]:
        ids: set[str] = set()
        for item in items:
            item_id = item.get("id")
            if not item_id:
                issues.append(ValidationIssue(f"missing_{kind}_id", f"{kind} sem id."))
                continue
            if item_id in ids:
                issues.append(ValidationIssue(f"duplicate_{kind}_id", f"{kind} duplicado: {item_id}"))
            ids.add(item_id)
        return ids


__all__ = ["AdventureValidator", "ValidationIssue"]
