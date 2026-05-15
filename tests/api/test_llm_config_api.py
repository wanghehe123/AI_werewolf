from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


def test_admin_can_create_model_provider_and_bind_role_to_it():
    client = TestClient(create_app())
    login = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    cookies = {"session_id": login.json()["data"]["session_id"]}

    provider_response = client.post(
        "/admin/llm/providers",
        json={
            "provider_id": "deepseek",
            "provider_type": "openai_compatible",
            "model_name": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
        cookies=cookies,
    )
    binding_response = client.post(
        "/admin/llm/role-bindings",
        json={"role_key": "werewolf", "provider_id": "deepseek"},
        cookies=cookies,
    )
    bindings = client.get("/admin/llm/role-bindings", cookies=cookies)

    assert provider_response.status_code == 201
    assert binding_response.status_code == 201
    assert provider_response.json()["code"] == 0
    assert binding_response.json()["code"] == 0
    assert any(
        binding["role_key"] == "werewolf" and binding["provider_id"] == "deepseek"
        for binding in bindings.json()["data"]
    )
