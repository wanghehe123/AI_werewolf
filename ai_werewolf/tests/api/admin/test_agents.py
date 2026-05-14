from fastapi.testclient import TestClient


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}


def test_admin_agent_crud(client: TestClient):
    cookies = login(client)
    payload = {
        "name": "冷静侦探",
        "avatar_url": None,
        "avatar_prompt": "冷静的年轻侦探，暗色背景",
        "persona": "理性、谨慎、会复盘票型",
        "speech_style": "短句克制",
        "reasoning_level": 5,
        "deception_level": 2,
        "aggression_level": 2,
        "cooperation_level": 4,
        "risk_preference": "balanced",
        "memory_style": "focus_on_votes",
        "default_model_provider_id": "deepseek",
        "enabled": True,
    }

    created = client.post("/admin/agents", json=payload, cookies=cookies)
    assert created.status_code == 201
    agent = created.json()["data"]
    assert agent["name"] == "冷静侦探"
    assert agent["avatar_prompt"] == "冷静的年轻侦探，暗色背景"

    listed = client.get("/admin/agents", cookies=cookies)
    assert any(item["agent_id"] == agent["agent_id"] for item in listed.json()["data"])

    updated = client.put(f"/admin/agents/{agent['agent_id']}", json={"enabled": False}, cookies=cookies)
    assert updated.json()["data"]["enabled"] is False

    deleted = client.delete(f"/admin/agents/{agent['agent_id']}", cookies=cookies)
    assert deleted.json()["code"] == 0
