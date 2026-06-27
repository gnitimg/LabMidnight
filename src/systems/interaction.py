"""Context interaction system public entrypoint."""

from __future__ import annotations

from src.systems.interaction_flow import InteractionFlowMixin
from src.systems.interaction_targeting import InteractionTargetingMixin
from src.systems.interaction_triggers import InteractionTriggerMixin


class InteractionSystem(InteractionTargetingMixin, InteractionFlowMixin, InteractionTriggerMixin):
    def __init__(self, game_map) -> None:
        self.game_map = game_map
