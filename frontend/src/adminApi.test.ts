import { afterEach, describe, expect, it, vi } from "vitest";

import { adminLogin, createAdminLlmProvider, fetchAdminLlmProviders, fetchAdminPlayers } from "./api";

describe("admin api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends credentials for admin requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, message: "ok", data: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchAdminPlayers("http://api.local");

    expect(fetchMock).toHaveBeenCalledWith("http://api.local/admin/players", { credentials: "include" });
  });

  it("logs in with query params and credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, message: "ok", data: { session_id: "s1" } })
    });
    vi.stubGlobal("fetch", fetchMock);

    await adminLogin("admin", "admin", "http://api.local");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.local/admin/login?username=admin&password=admin",
      { method: "POST", credentials: "include" }
    );
  });

  it("loads and creates LLM providers through authenticated admin endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, message: "ok", data: [] })
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchAdminLlmProviders("http://api.local");
    await createAdminLlmProvider(
      {
        provider_id: "deepseek",
        provider_type: "openai_compatible",
        model_name: "deepseek-chat",
        base_url: "https://api.deepseek.com/v1",
        api_key_env: "DEEPSEEK_API_KEY",
        temperature: 0.8,
        max_tokens: 1024,
        timeout: 30
      },
      "http://api.local"
    );

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://api.local/admin/llm/providers", { credentials: "include" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://api.local/admin/llm/providers",
      expect.objectContaining({ method: "POST", credentials: "include" })
    );
  });
});
