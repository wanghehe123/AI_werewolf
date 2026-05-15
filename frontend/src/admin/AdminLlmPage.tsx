import { FormEvent, useState } from "react";

import type { AdminLlmProviderDto, AdminRoleModelBindingDto } from "../types";

interface AdminLlmPageProps {
  providers: AdminLlmProviderDto[];
  bindings: AdminRoleModelBindingDto[];
  onRefresh: () => void;
  onCreateProvider?: (payload: AdminLlmProviderDto) => Promise<void>;
  onCreateBinding?: (payload: AdminRoleModelBindingDto) => Promise<void>;
}

export function AdminLlmPage({ providers, bindings, onRefresh, onCreateProvider, onCreateBinding }: AdminLlmPageProps) {
  const [providerId, setProviderId] = useState("");
  const [modelName, setModelName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKeyEnv, setApiKeyEnv] = useState("");
  const [roleKey, setRoleKey] = useState("werewolf");
  const [bindingProviderId, setBindingProviderId] = useState("");

  async function handleProviderSubmit(event: FormEvent) {
    event.preventDefault();
    if (!onCreateProvider || !providerId || !modelName) {
      return;
    }
    await onCreateProvider({
      provider_id: providerId,
      provider_type: providerId === "fake" ? "fake" : "openai_compatible",
      model_name: modelName,
      base_url: baseUrl || null,
      api_key_env: apiKeyEnv || null,
      temperature: 0.8,
      max_tokens: 1024,
      timeout: 30
    });
    setProviderId("");
    setModelName("");
    setBaseUrl("");
    setApiKeyEnv("");
    onRefresh();
  }

  async function handleBindingSubmit(event: FormEvent) {
    event.preventDefault();
    const selectedProvider = bindingProviderId || providers[0]?.provider_id;
    if (!onCreateBinding || !roleKey || !selectedProvider) {
      return;
    }
    await onCreateBinding({ role_key: roleKey, provider_id: selectedProvider });
    setBindingProviderId("");
    onRefresh();
  }

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="scene-kicker">LLM</p>
          <h2>模型配置</h2>
        </div>
        <button className="ghost-action" type="button" onClick={onRefresh}>
          刷新
        </button>
      </header>

      <div className="admin-split">
        <form className="admin-form-panel" onSubmit={handleProviderSubmit}>
          <h3>Provider</h3>
          <input aria-label="Provider ID" placeholder="Provider ID，如 deepseek" value={providerId} onChange={(event) => setProviderId(event.target.value)} />
          <input aria-label="模型名称" placeholder="模型名称，如 deepseek-chat" value={modelName} onChange={(event) => setModelName(event.target.value)} />
          <input aria-label="Base URL" placeholder="Base URL" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
          <input aria-label="API Key 环境变量" placeholder="API Key 环境变量" value={apiKeyEnv} onChange={(event) => setApiKeyEnv(event.target.value)} />
          <button className="primary-action" type="submit" disabled={!onCreateProvider}>
            新增 Provider
          </button>
        </form>

        <form className="admin-form-panel" onSubmit={handleBindingSubmit}>
          <h3>角色绑定</h3>
          <input aria-label="角色 Key" placeholder="角色 Key，如 werewolf" value={roleKey} onChange={(event) => setRoleKey(event.target.value)} />
          <select aria-label="绑定 Provider" value={bindingProviderId} onChange={(event) => setBindingProviderId(event.target.value)}>
            <option value="">选择 Provider</option>
            {providers.map((provider) => (
              <option key={provider.provider_id} value={provider.provider_id}>
                {provider.provider_id}
              </option>
            ))}
          </select>
          <button className="primary-action" type="submit" disabled={!onCreateBinding || providers.length === 0}>
            保存绑定
          </button>
        </form>
      </div>

      <div className="admin-table-grid">
        <div>
          <h3>Provider 列表</h3>
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>类型</th>
                <th>模型</th>
                <th>密钥</th>
              </tr>
            </thead>
            <tbody>
              {providers.map((provider) => (
                <tr key={provider.provider_id}>
                  <td>{provider.provider_id}</td>
                  <td>{provider.provider_type}</td>
                  <td>{provider.model_name}</td>
                  <td>{provider.api_key_env ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {providers.length === 0 ? <p className="admin-empty">暂无模型 Provider</p> : null}
        </div>

        <div>
          <h3>角色绑定</h3>
          <table className="admin-table">
            <thead>
              <tr>
                <th>角色</th>
                <th>Provider</th>
              </tr>
            </thead>
            <tbody>
              {bindings.map((binding) => (
                <tr key={binding.role_key}>
                  <td>{binding.role_key}</td>
                  <td>{binding.provider_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {bindings.length === 0 ? <p className="admin-empty">暂无角色绑定</p> : null}
        </div>
      </div>
    </section>
  );
}
