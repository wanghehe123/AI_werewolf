from fastapi.testclient import TestClient


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/login", params={"username": "admin", "password": "admin"})
    return {"session_id": response.json()["data"]["session_id"]}


def test_admin_roles_seed_and_list(client: TestClient):
    cookies = login(client)

    seeded = client.post("/admin/roles/seed", cookies=cookies)
    assert seeded.json()["code"] == 0

    listed = client.get("/admin/roles", cookies=cookies)
    role_keys = {role["role_key"] for role in listed.json()["data"]}
    assert {"werewolf", "seer", "witch", "hunter", "villager"}.issubset(role_keys)
