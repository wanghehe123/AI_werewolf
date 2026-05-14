import pytest
from unittest.mock import MagicMock, AsyncMock
from ai_werewolf.storage.admin_repository import PlayerRepository, AgentRepository, BoardRepository, RoleMetadataRepository

# Note: These tests use mocks since we don't have a real DB connection in test environment

def test_player_repository_crud():
    mock_session = MagicMock()
    repo = PlayerRepository(session=mock_session)

    # Mock create
    mock_player = MagicMock()
    mock_player.name = "测试"
    mock_player.is_ai = False
    mock_player.player_id = "test-id"

    def mock_add(obj):
        obj.player_id = "test-id"

    mock_session.add = MagicMock(side_effect=mock_add)
    mock_session.commit = MagicMock()
    mock_session.refresh = MagicMock()

    # Test create
    player = repo.create(name="测试", is_ai=False)
    assert player.name == "测试"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_player_repository_get_by_id():
    mock_session = MagicMock()
    repo = PlayerRepository(session=mock_session)

    mock_player = MagicMock()
    mock_player.player_id = "test-id"
    mock_player.name = "测试"
    mock_session.get = MagicMock(return_value=mock_player)

    result = repo.get_by_id("test-id")
    assert result is not None
    assert result.player_id == "test-id"


def test_player_repository_get_by_name():
    mock_session = MagicMock()
    repo = PlayerRepository(session=mock_session)

    mock_player = MagicMock()
    mock_player.name = "测试玩家"
    mock_session.exec.return_value.first.return_value = mock_player

    result = repo.get_by_name("测试玩家")
    assert result is not None
    assert result.name == "测试玩家"


def test_player_repository_list_all():
    mock_session = MagicMock()
    repo = PlayerRepository(session=mock_session)

    mock_players = [MagicMock(), MagicMock()]
    mock_session.exec.return_value.all.return_value = mock_players

    result = repo.list_all()
    assert len(result) == 2


def test_player_repository_update():
    mock_session = MagicMock()
    repo = PlayerRepository(session=mock_session)

    mock_player = MagicMock()
    mock_player.name = "旧名字"
    mock_session.get = MagicMock(return_value=mock_player)

    result = repo.update("test-id", name="新名字")
    assert result is not None
    mock_session.commit.assert_called_once()


def test_player_repository_delete():
    mock_session = MagicMock()
    repo = PlayerRepository(session=mock_session)

    mock_player = MagicMock()
    mock_session.get = MagicMock(return_value=mock_player)
    mock_session.delete = MagicMock()

    result = repo.delete("test-id")
    assert result is True
    mock_session.delete.assert_called_once()


def test_agent_repository_fields():
    mock_session = MagicMock()
    repo = AgentRepository(session=mock_session)

    # Test that repo accepts personality fields
    assert hasattr(repo, 'create')
    assert hasattr(repo, 'get_by_id')
    assert hasattr(repo, 'list_all')
    assert hasattr(repo, 'update')
    assert hasattr(repo, 'delete')


def test_agent_repository_create():
    mock_session = MagicMock()
    repo = AgentRepository(session=mock_session)

    def mock_add(obj):
        obj.agent_id = "agent-123"

    mock_session.add = MagicMock(side_effect=mock_add)
    mock_session.commit = MagicMock()
    mock_session.refresh = MagicMock()

    agent = repo.create(
        name="测试AI",
        persona="冷静理性",
        speech_style="正式",
        reasoning_level=4,
        deception_level=2
    )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_board_repository_crud():
    mock_session = MagicMock()
    repo = BoardRepository(session=mock_session)

    def mock_add(obj):
        obj.board_id = "board-123"

    mock_session.add = MagicMock(side_effect=mock_add)
    mock_session.commit = MagicMock()
    mock_session.refresh = MagicMock()

    board = repo.create(name="测试板子", min_players=6, max_players=12)
    assert board is not None
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_board_repository_add_role():
    mock_session = MagicMock()
    repo = BoardRepository(session=mock_session)

    def mock_add(obj):
        pass

    mock_session.add = MagicMock(side_effect=mock_add)
    mock_session.commit = MagicMock()

    role = repo.add_role("board-123", "werewolf", 2)
    assert role is not None
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


def test_board_repository_get_roles():
    mock_session = MagicMock()
    repo = BoardRepository(session=mock_session)

    mock_roles = [MagicMock(), MagicMock()]
    mock_session.exec.return_value.all.return_value = mock_roles

    result = repo.get_roles("board-123")
    assert len(result) == 2


def test_role_metadata_repository_list_all():
    mock_session = MagicMock()
    repo = RoleMetadataRepository(session=mock_session)

    mock_roles = [MagicMock()]
    mock_session.exec.return_value.all.return_value = mock_roles

    result = repo.list_all()
    assert len(result) == 1


def test_role_metadata_repository_get_by_key():
    mock_session = MagicMock()
    repo = RoleMetadataRepository(session=mock_session)

    mock_role = MagicMock()
    mock_role.role_key = "werewolf"
    mock_session.get = MagicMock(return_value=mock_role)

    result = repo.get_by_key("werewolf")
    assert result is not None
    assert result.role_key == "werewolf"