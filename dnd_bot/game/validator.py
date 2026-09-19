"""Validação estrutural e semântica básica do estado de uma campanha.

O validador não decide regras narrativas. Ele apenas detecta referências
quebradas e inconsistências que fariam o simulador ou o GameEngine operar sobre
um estado impossível.
"""

from __future__ import annotations

from dataclasses import dataclass

from .adventure import AdventureState


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


class AdventureValidator:
    """Valida invariantes estruturais importantes do AdventureState."""

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

        current = progress.get("local_atual")
        if current not in location_ids:
            issues.append(ValidationIssue(
                "invalid_current_location",
                f"Local atual inexistente: {current}",
            ))

        discovered = set(progress.get("locais_descobertos", []))
        visited = set(progress.get("locais_visitados", []))

        for location_id in discovered:
            if location_id not in location_ids:
                issues.append(ValidationIssue(
                    "broken_discovered_location",
                    f"Local descoberto inexistente: {location_id}",
                ))

        for location_id in visited:
            if location_id not in location_ids:
                issues.append(ValidationIssue(
                    "broken_visited_location",
                    f"Local visitado inexistente: {location_id}",
                ))

        if current in location_ids and current not in discovered:
            issues.append(ValidationIssue(
                "current_location_not_discovered",
                f"Local atual não está descoberto: {current}",
            ))

        for location in locations:
            location_id = location.get("id")
            for connection in location.get("conexoes", []):
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

        for npc in npcs:
            if npc.get("local_atual") not in location_ids:
                issues.append(ValidationIssue(
                    "broken_npc_location",
                    f"NPC {npc.get('id')} está em local inexistente: {npc.get('local_atual')}",
                ))
            for secret_id in npc.get("segredos", []):
                if secret_id not in secret_ids:
                    issues.append(ValidationIssue(
                        "broken_npc_secret",
                        f"NPC {npc.get('id')} referencia segredo inexistente: {secret_id}",
                    ))

        for encounter in encounters:
            if encounter.get("local") not in location_ids:
                issues.append(ValidationIssue(
                    "broken_encounter_location",
                    f"Encounter {encounter.get('id')} está em local inexistente: {encounter.get('local')}",
                ))

        for quest in quests:
            quest_id = quest.get("id")
            step_ids: set[str] = set()
            steps = quest.get("etapas", [])
            for step in steps:
                step_id = step.get("id")
                if step_id in step_ids:
                    issues.append(ValidationIssue(
                        "duplicate_quest_step",
                        f"Quest {quest_id} possui etapa duplicada: {step_id}",
                    ))
                step_ids.add(step_id)

            if steps and all(step.get("status") == "concluida" for step in steps):
                if quest.get("status") != "concluida":
                    issues.append(ValidationIssue(
                        "quest_status_inconsistent",
                        f"Quest {quest_id} tem todas as etapas concluídas, mas status={quest.get('status')}.",
                    ))

        for item in items:
            local_id = item.get("local_atual")
            if local_id is not None and local_id not in location_ids:
                issues.append(ValidationIssue(
                    "broken_item_location",
                    f"Item {item.get('id')} está em local inexistente: {local_id}",
                ))

        completed_encounters = set(progress.get("encounters_concluidos", []))
        for encounter_id in completed_encounters:
            if encounter_id not in encounter_ids:
                issues.append(ValidationIssue(
                    "broken_completed_encounter",
                    f"Encounter concluído inexistente: {encounter_id}",
                ))

        completed_quests = set(progress.get("quests_concluidas", []))
        for quest_id in completed_quests:
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
        issues = self.validate(state)
        if issues:
            details = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
            raise ValueError(f"Estado de campanha inválido: {details}")

    @staticmethod
    def _unique_ids(items, kind: str, issues: list[ValidationIssue]) -> set[str]:
        ids: set[str] = set()
        for item in items:
            item_id = item.get("id")
            if not item_id:
                issues.append(ValidationIssue(
                    f"missing_{kind}_id",
                    f"{kind} sem id.",
                ))
                continue
            if item_id in ids:
                issues.append(ValidationIssue(
                    f"duplicate_{kind}_id",
                    f"{kind} duplicado: {item_id}",
                ))
            ids.add(item_id)
        return ids


__all__ = ["AdventureValidator", "ValidationIssue"]
