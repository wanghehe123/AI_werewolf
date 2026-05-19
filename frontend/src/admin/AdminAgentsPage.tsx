import { useState } from "react";

import type { AdminAgentDto, AdminLlmProviderDto } from "../types";
import { AgentFormModal, type AgentFormValues } from "./AgentFormModal";

interface AdminAgentsPageProps {
  agents: AdminAgentDto[];
  onRefresh: () => void;
  onShowCreate: () => void;
  onCreateSubmit: (values: AgentFormValues) => Promise<void> | void;
  onUpdateSubmit: (agentId: string, values: AgentFormValues) => Promise<void> | void;
  onToggleEnabled?: (agent: AdminAgentDto) => Promise<void>;
  onDelete?: (agentId: string) => Promise<void>;
  providers?: AdminLlmProviderDto[];
}

export function AdminAgentsPage({
  agents,
  onRefresh,
  onShowCreate,
  onCreateSubmit,
  onUpdateSubmit,
  onToggleEnabled,
  onDelete,
  providers = [],
}: AdminAgentsPageProps) {
  const [editingAgent, setEditingAgent] = useState<AdminAgentDto | null>(null);

  const providerOptions = providers.map((p) => ({
    provider_id: p.provider_id,
    name: p.model_name ? `${p.provider_id} (${p.model_name})` : p.provider_id,
  }));

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">AGENTS</p>
          <h2>AI 人设管理</h2>
        </div>
        <div className="admin-actions">
          <button className="primary-action" type="button" onClick={onShowCreate}>
            + 新建 AI
          </button>
          <button className="ghost-action" type="button" onClick={onRefresh}>
            刷新
          </button>
        </div>
      </header>

      {agents.length === 0 ? (
        <div className="admin-empty-state">
          <p>暂无 AI 人设</p>
          <button className="primary-action" type="button" onClick={onShowCreate}>
            创建第一个 AI
          </button>
        </div>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>人格</th>
              <th>风格</th>
              <th>风险</th>
              <th>模型</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr key={agent.agent_id}>
                <td>{agent.name}</td>
                <td>{agent.persona}</td>
                <td>{agent.speech_style}</td>
                <td>{RISK_LABELS[agent.risk_preference] ?? agent.risk_preference}</td>
                <td>{agent.default_model_provider_id ?? "-"}</td>
                <td>{agent.enabled ? "启用" : "停用"}</td>
                <td>
                  <span className="admin-row-actions">
                    <button
                      className="ghost-action compact"
                      type="button"
                      onClick={() => setEditingAgent(agent)}
                    >
                      编辑
                    </button>
                    <button className="ghost-action compact" type="button" onClick={() => void onToggleEnabled?.(agent)}>
                      {agent.enabled ? "停用" : "启用"}
                    </button>
                    <button
                      className="danger-action compact"
                      type="button"
                      onClick={() => {
                        if (window.confirm(`确定删除 AI「${agent.name}」？`)) {
                          void onDelete?.(agent.agent_id);
                        }
                      }}
                    >
                      删除
                    </button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Edit modal */}
      {editingAgent ? (
        <AgentFormModal
          isOpen={true}
          onClose={() => setEditingAgent(null)}
          onSubmit={async (values) => {
            await onUpdateSubmit(editingAgent.agent_id, values);
            await onRefresh();
            return {};
          }}
          initialValues={{
            agent_id: editingAgent.agent_id,
            name: editingAgent.name,
            avatar_url: editingAgent.avatar_url,
            avatar_prompt: editingAgent.avatar_prompt,
            persona: editingAgent.persona,
            speech_style: editingAgent.speech_style,
            reasoning_level: editingAgent.reasoning_level,
            deception_level: editingAgent.deception_level,
            aggression_level: editingAgent.aggression_level,
            cooperation_level: editingAgent.cooperation_level,
            risk_preference: editingAgent.risk_preference,
            memory_style: editingAgent.memory_style,
            default_model_provider_id: editingAgent.default_model_provider_id ?? null,
            enabled: editingAgent.enabled,
          }}
          providers={providerOptions}
        />
      ) : null}
    </section>
  );
}

const RISK_LABELS: Record<string, string> = {
  conservative: "保守",
  balanced: "均衡",
  aggressive: "激进",
};
