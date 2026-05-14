import { afterEach, describe, expect, it, vi } from "vitest";

import { adminLogin, fetchAdminPlayers } from "./api";

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
});
