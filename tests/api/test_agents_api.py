from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_admin_can_create_agent_persona():
    client = TestClient(create_app())
    login = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    cookies = {"session_id": login.json()["data"]["session_id"]}
    payload = {
        "agent_id": "agent_custom",
        "name": "后台智能体",
        "avatar_url": None,
        "avatar_prompt": "冷静的年轻侦探",
        "persona": "理性谨慎",
        "speech_style": "短句克制",
        "reasoning_level": 5,
        "deception_level": 3,
        "aggression_level": 2,
        "cooperation_level": 4,
        "risk_preference": "balanced",
        "memory_style": "focus_on_votes",
        "enabled": True,
    }

    response = client.post("/admin/agents", json=payload, cookies=cookies)

    assert response.status_code == 201
    assert response.json()["code"] == 0
    assert response.json()["data"]["agent_id"] == "agent_custom"
