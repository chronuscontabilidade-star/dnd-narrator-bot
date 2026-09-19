"""Decisões coletivas da party.

Esta camada não resolve regras de D&D. Ela apenas transforma uma oportunidade
narrativa em decisão -> votos -> resolução determinística.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PartyDecision:
    """Uma decisão apresentada à party."""

    id: str
    prompt: str
    options: tuple[str, ...]
    reason: str
    source: str = "director"

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Decision precisa de id.")
        if not self.prompt.strip():
            raise ValueError("Decision precisa de prompt.")
        if not self.options:
            raise ValueError("Decision precisa de pelo menos uma opção.")
        if len(set(self.options)) != len(self.options):
            raise ValueError("Decision não pode ter opções duplicadas.")


@dataclass(frozen=True)
class PartyVote:
    """Voto individual de um membro."""

    voter_id: str
    option: str


@dataclass(frozen=True)
class DecisionResolution:
    """Resultado puro de uma votação."""

    decision_id: str
    accepted: bool
    selected_option: str | None
    executor_id: str | None
    votes: tuple[PartyVote, ...]
    counts: dict[str, int]
    tied: bool
    reason: str


class PartyDecisionResolver:
    """Resolve votações sem tocar no estado da campanha.

    Uma opção precisa de maioria absoluta dos votos válidos.
    Assim, em uma party de 4 jogadores, 2x2 não executa nada.
    """

    def resolve(
        self,
        decision: PartyDecision,
        votes: Iterable[PartyVote],
    ) -> DecisionResolution:
        votes = tuple(votes)
        allowed = set(decision.options)

        if not votes:
            return DecisionResolution(
                decision_id=decision.id,
                accepted=False,
                selected_option=None,
                executor_id=None,
                votes=(),
                counts={option: 0 for option in decision.options},
                tied=False,
                reason="Nenhum voto foi registrado.",
            )

        seen: set[str] = set()
        valid_votes: list[PartyVote] = []
        for vote in votes:
            if not vote.voter_id.strip():
                raise ValueError("Voto precisa de voter_id.")
            if vote.voter_id in seen:
                raise ValueError(f"Voto duplicado para o jogador: {vote.voter_id}")
            if vote.option not in allowed:
                raise ValueError(f"Opção inválida no voto: {vote.option}")
            seen.add(vote.voter_id)
            valid_votes.append(vote)

        counts = Counter(vote.option for vote in valid_votes)
        for option in decision.options:
            counts.setdefault(option, 0)

        highest = max(counts.values())
        winners = [option for option in decision.options if counts[option] == highest]
        majority = len(valid_votes) // 2 + 1
        accepted = len(winners) == 1 and highest >= majority

        selected = winners[0] if accepted else None
        executor = None
        if selected is not None:
            executor = next(
                vote.voter_id for vote in valid_votes if vote.option == selected
            )

        if accepted:
            reason = f"Maioria absoluta: {highest}/{len(valid_votes)} votos."
        elif len(winners) > 1:
            reason = "Empate: a decisão foi rejeitada sem alterar o estado."
        else:
            reason = (
                f"Sem maioria absoluta: {highest}/{len(valid_votes)} votos."
            )

        return DecisionResolution(
            decision_id=decision.id,
            accepted=accepted,
            selected_option=selected,
            executor_id=executor,
            votes=tuple(valid_votes),
            counts=dict(counts),
            tied=len(winners) > 1,
            reason=reason,
        )


__all__ = [
    "DecisionResolution",
    "PartyDecision",
    "PartyDecisionResolver",
    "PartyVote",
]
