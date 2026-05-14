import { FormEvent, useState } from "react";

import type { AdminAgentDto } from "../types";

interface AdminAgentsPageProps {
  agents: AdminAgentDto[];
  onRefresh: () => void;
  onCreate?: (payload: Partial<AdminAgentDto> & { name: string; persona: string; speech_style: string }) => Promise<void>;
}

export function AdminAgentsPage({ agents, onRefresh, onCreate }: AdminAgentsPageProps) {
  const [name, setName] = useState("");
  const [persona, setPersona] = useState("");
  const [speechStyle, setSpeechStyle] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!onCreate || !name || !persona || !speechStyle) {
      return;
    }
    await onCreate({
      name,
      persona,
      speech_style: speechStyle,
      reasoning_level: 3,
      deception_level: 3,
      aggression_level: 3,
      cooperation_level: 3,
      risk_preference: "balanced",
      memory_style: "focus_on_votes",
      enabled: true
    });
    setName("");
    setPersona("");
    setSpeechStyle("");
    onRefresh();
  }

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">AGENTS</p>
          <h2>AI 人设管理</h2>
        </div>
        <button className="ghost-action" type="button" onClick={onRefresh}>
          刷新
        </button>
      </header>
      <form className="admin-inline-form" onSubmit={handleSubmit}>
        <input aria-label="AI 名称" placeholder="AI 名称" value={name} onChange={(event) => setName(event.target.value)} />
        <input aria-label="人格" placeholder="人格" value={persona} onChange={(event) => setPersona(event.target.value)} />
        <input aria-label="发言风格" placeholder="发言风格" value={speechStyle} onChange={(event) => setSpeechStyle(event.target.value)} />
        <button className="primary-action" type="submit" disabled={!onCreate}>
          新增 AI
        </button>
      </form>
      <table className="admin-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>人格</th>
            <th>风格</th>
            <th>模型</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr key={agent.agent_id}>
              <td>{agent.name}</td>
              <td>{agent.persona}</td>
              <td>{agent.speech_style}</td>
              <td>{agent.default_model_provider_id ?? "-"}</td>
              <td>{agent.enabled ? "启用" : "停用"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {agents.length === 0 ? <p className="admin-empty">暂无 AI 人设</p> : null}
    </section>
  );
}
