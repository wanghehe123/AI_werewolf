import { FormEvent, useState } from "react";

interface AdminLoginPageProps {
  login: (username: string, password: string) => Promise<void>;
}

export function AdminLoginPage({ login }: AdminLoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="admin-login">
      <section className="admin-login-panel">
        <p className="scene-kicker">ADMIN CONSOLE</p>
        <h1>后台管理</h1>
        <form onSubmit={handleSubmit} className="admin-form">
          <label>
            用户名
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            密码
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <p className="error-text">{error}</p> : null}
          <button className="primary-action" type="submit" disabled={pending}>
            登录
          </button>
        </form>
      </section>
    </main>
  );
}
