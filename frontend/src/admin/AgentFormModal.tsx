import { FormEvent, useState } from "react";

interface ProviderOption {
  provider_id: string;
  name: string;
}

interface AgentFormValues {
  agent_id?: string;
  name: string;
  persona: string;
  speech_style: string;
  reasoning_level: number;
  deception_level: number;
  aggression_level: number;
  cooperation_level: number;
  risk_preference: string;
  memory_style: string;
  default_model_provider_id?: string | null;
  enabled: boolean;
}

interface AgentFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (values: AgentFormValues) => Promise<unknown>;
  initialValues?: AgentFormValues;
  providers?: ProviderOption[];
}

const DEFAULT_VALUES: AgentFormValues = {
  name: "",
  persona: "",
  speech_style: "",
  reasoning_level: 3,
  deception_level: 3,
  aggression_level: 3,
  cooperation_level: 3,
  risk_preference: "balanced",
  memory_style: "focus_on_votes",
  default_model_provider_id: null,
  enabled: true,
};

const RISK_OPTIONS = [
  { value: "conservative", label: "保守" },
  { value: "balanced", label: "均衡" },
  { value: "aggressive", label: "激进" },
];

const MEMORY_OPTIONS = [
  { value: "focus_on_votes", label: "关注投票" },
  { value: "detail_oriented", label: "细节导向" },
  { value: "pattern_aware", label: "模式感知" },
];

function SliderInput({
  label,
  value,
  onChange,
  min = 1,
  max = 5,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <div className="admin-form-row">
      <label className="admin-slider-label">
        {label}
        <span className="admin-slider-value">{value}</span>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="admin-slider"
      />
    </div>
  );
}

export function AgentFormModal({ isOpen, onClose, onSubmit, initialValues, providers = [] }: AgentFormModalProps) {
  const [values, setValues] = useState<AgentFormValues>(initialValues ?? DEFAULT_VALUES);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  function update<K extends keyof AgentFormValues>(key: K, value: AgentFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!values.name.trim()) {
      setMessage("请填写 AI 名称");
      return;
    }
    if (!values.persona.trim()) {
      setMessage("请填写人格描述");
      return;
    }
    if (!values.speech_style.trim()) {
      setMessage("请填写发言风格");
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      await onSubmit(values);
      setValues(DEFAULT_VALUES);
      onClose();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  }

  const isEdit = !!initialValues;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal-title">{isEdit ? "编辑 AI" : "新建 AI"}</h3>

        <form className="admin-form" onSubmit={handleSubmit}>
          <div className="admin-form-row">
            <label htmlFor="agent-name">AI 名称</label>
            <input
              id="agent-name"
              aria-label="AI 名称"
              value={values.name}
              onChange={(e) => update("name", e.target.value)}
              placeholder="如: 林野"
            />
          </div>

          <div className="admin-form-row">
            <label htmlFor="agent-persona">人格</label>
            <input
              id="agent-persona"
              aria-label="人格"
              value={values.persona}
              onChange={(e) => update("persona", e.target.value)}
              placeholder="如: 理性、谨慎、喜欢分析数据"
            />
          </div>

          <div className="admin-form-row">
            <label htmlFor="agent-style">发言风格</label>
            <input
              id="agent-style"
              aria-label="发言风格"
              value={values.speech_style}
              onChange={(e) => update("speech_style", e.target.value)}
              placeholder="如: 简洁有力，多用短句"
            />
          </div>

          <div className="admin-sliders">
            <SliderInput label="推理能力" value={values.reasoning_level} onChange={(v) => update("reasoning_level", v)} />
            <SliderInput label="欺骗能力" value={values.deception_level} onChange={(v) => update("deception_level", v)} />
            <SliderInput label="攻击性" value={values.aggression_level} onChange={(v) => update("aggression_level", v)} />
            <SliderInput label="合作性" value={values.cooperation_level} onChange={(v) => update("cooperation_level", v)} />
          </div>

          <div className="admin-form-row">
            <label htmlFor="agent-risk">风险偏好</label>
            <select
              id="agent-risk"
              value={values.risk_preference}
              onChange={(e) => update("risk_preference", e.target.value)}
            >
              {RISK_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="admin-form-row">
            <label htmlFor="agent-memory">记忆风格</label>
            <select
              id="agent-memory"
              value={values.memory_style}
              onChange={(e) => update("memory_style", e.target.value)}
            >
              {MEMORY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {providers.length > 0 ? (
            <div className="admin-form-row">
              <label htmlFor="agent-provider">默认模型</label>
              <select
                id="agent-provider"
                value={values.default_model_provider_id ?? ""}
                onChange={(e) => update("default_model_provider_id", e.target.value || null)}
              >
                <option value="">不指定</option>
                {providers.map((p) => (
                  <option key={p.provider_id} value={p.provider_id}>{p.name}</option>
                ))}
              </select>
            </div>
          ) : null}

          <div className="admin-form-actions">
            <button className="primary-action" type="submit" disabled={submitting}>
              {submitting ? "保存中..." : "确认"}
            </button>
            <button className="ghost-action" type="button" onClick={onClose}>
              取消
            </button>
          </div>
          {message ? <p className="admin-form-message" role="alert">{message}</p> : null}
        </form>
      </div>
    </div>
  );
}
