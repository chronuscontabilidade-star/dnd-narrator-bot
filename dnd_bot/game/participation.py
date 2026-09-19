"""Participação individual em decisões da party.

A decisão coletiva escolhe o objetivo da cena. A participação determina quais
personagens se envolvem nessa ação. Esta camada não aplica regras nem altera
AdventureState.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PartyParticipation:
    """Declara a participação de um personagem na decisão aprovada."""

    player_id: str
    action: str
    participate: bool = True

    def __post_init__(self) -> None:
        if not self.player_id.strip():
            raise ValueError("Participação precisa de player_id.")
        if self.participate and not self.action.strip():
            raise ValueError("Participante precisa informar uma ação.")


@dataclass(frozen=True)
class ParticipationResolution:
    """Resultado puro da participação individual."""

    decision_id: str
    selected_option: str
    participants: tuple[PartyParticipation, ...]
    declined: tuple[str, ...]
    reason: str


class PartyParticipationResolver:
    """Valida e consolida a participação sem resolver testes de D&D."""

    def resolve(
        self,
        decision_id: str,
        selected_option: str,
        participations: Iterable[PartyParticipation],
    ) -> ParticipationResolution:
        if not decision_id.strip():
            raise ValueError("Participação precisa de decision_id.")
        if not selected_option.strip():
            raise ValueError("Participação precisa de selected_option.")

        seen: set[str] = set()
        participants: list[PartyParticipation] = []
        declined: list[str] = []

        for item in participations:
            if item.player_id in seen:
                raise ValueError(
                    f"Participação duplicada para o jogador: {item.player_id}"
                )
            seen.add(item.player_id)

            if item.participate:
                participants.append(item)
            else:
                declined.append(item.player_id)

        if not participants:
            reason = "Nenhum personagem participou; a decisão não gera ação."
        else:
            reason = (
                f"{len(participants)} participante(s), "
                f"{len(declined)} personagem(ns) optaram por não participar."
            )

        return ParticipationResolution(
            decision_id=decision_id,
            selected_option=selected_option,
            participants=tuple(participants),
            declined=tuple(declined),
            reason=reason,
        )


__all__ = [
    "PartyParticipation",
    "PartyParticipationResolver",
    "ParticipationResolution",
]
