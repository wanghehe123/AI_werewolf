import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AdminLoginPage } from "./AdminLoginPage";

describe("AdminLoginPage", () => {
  it("submits admin credentials", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    render(<AdminLoginPage login={login} />);

    await userEvent.type(screen.getByLabelText("用户名"), "admin");
    await userEvent.type(screen.getByLabelText("密码"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "登录" }));

    expect(login).toHaveBeenCalledWith("admin", "admin");
  });
});
