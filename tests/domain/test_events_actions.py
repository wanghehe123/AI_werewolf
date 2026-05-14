from ai_werewolf.domain.actions import PlayerAction, PlayerActionType
from ai_werewolf.domain.events import GameEvent, GameEventType


def test_player_action_represents_vote_target():
    action = PlayerAction(
        actor_id="p1",
        action_type=PlayerActionType.VOTE,
        target_id="p2",
        reason="p2 发言前后矛盾",
    )

    assert action.action_type == PlayerActionType.VOTE
    assert action.target_id == "p2"


def test_game_event_has_public_visibility_flag():
    event = GameEvent(
        event_type=GameEventType.SPEECH,
        actor_id="p1",
        target_id=None,
        payload={"speech": "我先听后置位。"},
        public=True,
    )

    assert event.public is True
