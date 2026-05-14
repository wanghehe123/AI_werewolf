from ai_werewolf.storage.models import Player, RoleMetadata, Board, BoardRole

def test_player_can_be_created():
    player = Player(name="测试玩家", is_ai=False)
    assert player.name == "测试玩家"
    assert player.is_ai == False
    assert player.player_id is not None

def test_role_metadata_fields():
    role = RoleMetadata(role_key="werewolf", name="狼人", faction="wolf", description="夜里杀人")
    assert role.role_key == "werewolf"
    assert role.faction == "wolf"

def test_board_has_roles():
    board = Board(name="测试板子", min_players=6, max_players=8)
    role = BoardRole(role_key="werewolf", count=2)
    board.roles.append(role)
    assert len(board.roles) == 1