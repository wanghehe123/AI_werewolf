import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import type { GameStateDto, PlayerActionOptionDto, SubmitActionInput } from "../types";
import { currentActionKind, selectablePlayerIds, phaseLabel } from "./gameVisuals";

interface ActionDockProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
  selectedTargetId: string | null;
  onSelectTarget: (playerId: string | null) => void;
}

export function ActionDock({
  game,
  onSubmitAction,
  pending,
  selectedTargetId,
  onSelectTarget,
}: ActionDockProps) {
  const actionKind = currentActionKind(game);
  const primaryAction = game.allowed_actions[0];
  const humanPlayer = game.players.find((p) => p.player_id === game.human_player_id);
  const isAlive = humanPlayer?.alive ?? true;

  // Speech state
  const [speech, setSpeech] = useState("我先听发言，今天重点看谁的逻辑变化。");
  // Vote target
  const aliveTargets = useMemo(
    () => game.players.filter((p) => p.alive && !p.is_human),
    [game.players]
  );

  // Sync selected target with action changes
  useEffect(() => {
    const selectable = selectablePlayerIds(game);
    if (selectable.length > 0 && (!selectedTargetId || !selectable.includes(selectedTargetId))) {
      onSelectTarget(selectable[0]);
    }
  }, [game.allowed_actions, selectedTargetId, onSelectTarget]);

  const canVote = game.allowed_actions.some((a) => a.action_type === "vote");
  const canAbstain = game.allowed_actions.some((a) => a.action_type === "abstain");

  if (actionKind === "sheriff_election") {
    const canRun = game.allowed_actions.some((a) => a.action_type === "run_for_sheriff");
    const canSkip = game.allowed_actions.some((a) => a.action_type === "skip_election");
    return (
      <DockWrapper>
        <p className="text-xs tracking-[0.15em] uppercase text-[var(--color-gold)] mb-2">SHERIFF</p>
        <h3 className="text-base font-bold mb-2">警长竞选报名</h3>
        <p className="text-sm text-[var(--color-text-dim)] mb-3">
          这一轮先决定是否上警。候选人稍后会依次发言，其他人负责投票。
        </p>
        <div className="flex gap-3">
          <DockButton
            disabled={pending || !canRun}
            onClick={() => onSubmitAction({ action_type: "run_for_sheriff" })}
          >
            参加竞选
          </DockButton>
          <button
            className="px-4 py-2 rounded-lg border border-[var(--color-warm-border)] bg-transparent text-[var(--color-text)] text-sm hover:bg-[var(--color-warm-card)] disabled:opacity-50"
            disabled={pending || !canSkip}
            onClick={() => onSubmitAction({ action_type: "skip_election" })}
          >
            不参加
          </button>
        </div>
      </DockWrapper>
    );
  }

  // ── Setup ──
  if (game.phase === "setup") {
    return (
      <DockWrapper>
        <p className="text-sm text-[var(--color-text-dim)] mb-3">座位和身份已由后端分配。点击开始后，房间进入第一夜。</p>
        <DockButton disabled={pending} onClick={() => onSubmitAction({ action_type: "start_game" })}>
          开始游戏
        </DockButton>
      </DockWrapper>
    );
  }

  // ── Observer (no actions) ──
  if (actionKind === "observer") {
    return (
      <DockWrapper>
        <p className="text-sm text-[var(--color-text-dim)]">
          {isAlive ? "等待其他玩家行动中..." : "你已出局，正在旁观。"}
        </p>
      </DockWrapper>
    );
  }

  // ── Night: witch start ──
  if (actionKind === "night_start") {
    return (
      <DockWrapper night>
        <p className="text-sm text-[var(--color-text-dim)] mb-3">你是女巫。夜晚降临，点击开始后决定是否使用药水。</p>
        <DockButton disabled={pending} onClick={() => onSubmitAction({ action_type: "night_start" })}>
          开始夜晚
        </DockButton>
      </DockWrapper>
    );
  }

  // ── Night: witch action ──
  if (actionKind === "witch_action") {
    return (
      <WitchActionDock
        game={game}
        pending={pending}
        selectedTargetId={selectedTargetId}
        onSelectTarget={onSelectTarget}
        onSubmitAction={onSubmitAction}
      />
    );
  }

  // ── Night: target selection ──
  if (actionKind === "night_target") {
    return (
      <DockWrapper night>
        <p className="text-xs tracking-[0.15em] uppercase text-[var(--color-blue-night)] mb-2">NIGHT</p>
        <h3 className="text-base font-bold mb-3">{primaryAction?.label ?? "夜晚行动"}</h3>
        <p className="text-sm text-[var(--color-text-dim)] mb-3">
          {selectedTargetId
            ? `目标：${game.players.find((p) => p.player_id === selectedTargetId)?.seat ?? ""}号 ${game.players.find((p) => p.player_id === selectedTargetId)?.display_name ?? ""}`
            : "点击座位选择目标"}
        </p>
        <DockButton
          disabled={pending || !selectedTargetId}
          onClick={() => onSubmitAction({ action_type: primaryAction!.action_type, target_player_id: selectedTargetId! })}
        >
          {primaryAction?.label ?? "确认"}
        </DockButton>
      </DockWrapper>
    );
  }

  // ── Speech ──
  if (actionKind === "speech" || actionKind === "sheriff_speech") {
    const isSheriffSpeech = actionKind === "sheriff_speech";
    return (
      <DockWrapper>
        <p className="text-xs text-[var(--color-gold)] mb-1">{isSheriffSpeech ? "你正在竞选发言" : "你正在发言"}</p>
        <textarea
          aria-label="发言内容"
          className="w-full p-3 rounded-lg border border-[var(--color-warm-border)] bg-[var(--color-warm-bg)] text-[var(--color-text)] resize-y min-h-[80px] text-sm"
          value={speech}
          onChange={(e) => setSpeech(e.target.value)}
          rows={3}
        />
        <div className="flex gap-2 mt-2">
          {isSheriffSpeech ? (
            <>
              <QuickTemplate label="我来带队" onClick={() => setSpeech("我愿意上警带队，把发言和票型梳理清楚。")} />
              <QuickTemplate label="重视逻辑" onClick={() => setSpeech("我上警会优先盘逻辑和票线，不会随便带偏节奏。")} />
            </>
          ) : (
            <>
              <QuickTemplate label="我先报信息" onClick={() => setSpeech("我有一些信息要分享。")} />
              <QuickTemplate label="我先听后置位" onClick={() => setSpeech("我先听后置位发言再做判断。")} />
            </>
          )}
        </div>
        <DockButton
          disabled={pending || speech.trim().length === 0}
          onClick={() => onSubmitAction({ action_type: "speech", content: speech })}
        >
          {isSheriffSpeech ? "提交竞选发言" : "提交发言"}
        </DockButton>
      </DockWrapper>
    );
  }

  // ── Vote ──
  if (actionKind === "vote" || actionKind === "sheriff_vote") {
    const targetPlayer = game.players.find((p) => p.player_id === selectedTargetId);
    const isSheriffVote = actionKind === "sheriff_vote";
    return (
      <DockWrapper>
        <p className="text-xs tracking-[0.15em] uppercase text-[var(--color-gold)] mb-2">VOTE</p>
        <h3 className="text-base font-bold mb-2">{isSheriffVote ? "警长投票" : "放逐投票"}</h3>
        <p className="text-sm text-[var(--color-text-dim)] mb-3">
          {targetPlayer
            ? `你将投给：${targetPlayer.seat}号 ${targetPlayer.display_name}`
            : `点击座位选择${isSheriffVote ? "警长候选人" : "投票目标"}`}
        </p>
        <div className="flex gap-3">
          <DockButton disabled={pending || !selectedTargetId || !canVote} onClick={() => onSubmitAction({ action_type: "vote", target_player_id: selectedTargetId! })}>
            {isSheriffVote ? "投给他" : "投票"}
          </DockButton>
          <button
            className="px-4 py-2 rounded-lg border border-[var(--color-warm-border)] bg-transparent text-[var(--color-text)] text-sm hover:bg-[var(--color-warm-card)] disabled:opacity-50"
            disabled={pending || !canAbstain}
            onClick={() => onSubmitAction({ action_type: "abstain" })}
          >
            {isSheriffVote ? "弃选票" : "弃票"}
          </button>
        </div>
      </DockWrapper>
    );
  }

  // ── Continue (generic) ──
  return (
    <DockWrapper>
      <p className="text-sm text-[var(--color-text-dim)] mb-3">
        {game.public_events.at(-1)?.payload.message ?? `${phaseLabel(game.phase)}阶段`}
      </p>
      <DockButton disabled={pending} onClick={() => onSubmitAction({ action_type: primaryAction?.action_type ?? "continue" })}>
        {primaryAction?.label ?? "继续"}
      </DockButton>
    </DockWrapper>
  );
}

/* ── Witch sub-dock ── */

function WitchActionDock({
  game,
  pending,
  selectedTargetId,
  onSelectTarget,
  onSubmitAction,
}: {
  game: GameStateDto;
  pending: boolean;
  selectedTargetId: string | null;
  onSelectTarget: (id: string | null) => void;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
}) {
  const actions = game.allowed_actions;
  const primaryAction = actions[0];
  const killInfo = primaryAction?.night_kill_info;
  const saveAction = actions.find((a) => a.action_type === "witch_save");
  const poisonAction = actions.find((a) => a.action_type === "witch_poison");
  const noAction = actions.find((a) => a.action_type === "no_action");
  const poisonTargets = poisonAction?.target_options ?? [];

  const [selectedAction, setSelectedAction] = useState<string>("none");
  const [poisonTarget, setPoisonTarget] = useState(poisonTargets[0]?.player_id ?? "");

  const handleSubmit = () => {
    if (selectedAction === "save" && saveAction) {
      onSubmitAction({ action_type: "witch_save", target_player_id: killInfo!.target_id });
    } else if (selectedAction === "poison" && poisonTarget) {
      onSubmitAction({ action_type: "witch_poison", target_player_id: poisonTarget });
    } else {
      onSubmitAction({ action_type: "no_action" });
    }
  };

  return (
    <DockWrapper night>
      <p className="text-xs tracking-[0.15em] uppercase text-[var(--color-purple-llm)] mb-2">NIGHT — 女巫</p>
      <h3 className="text-base font-bold mb-2">夜晚行动</h3>

      {killInfo && (
        <div className="p-3 rounded-lg bg-red-900/20 border border-red-800/40 mb-3">
          <p className="text-sm font-semibold text-red-300">
            今晚 {killInfo.target_label} 被狼人击杀。
          </p>
          {!killInfo.can_save && killInfo.reason && (
            <p className="text-xs text-red-400 mt-1">{killInfo.reason}</p>
          )}
        </div>
      )}

      <div className="space-y-2">
        {saveAction && killInfo?.can_save && (
          <label className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer text-sm transition-colors ${selectedAction === "save" ? "border-green-500 bg-green-900/20" : "border-[var(--color-warm-border)] bg-[var(--color-warm-bg)]"}`}>
            <input type="radio" name="witch-action" checked={selectedAction === "save"} onChange={() => setSelectedAction("save")} />
            <span className="text-green-400">使用解药救活 {killInfo.target_label}</span>
          </label>
        )}

        {poisonAction && (
          <div className={`p-2 rounded-lg border transition-colors ${selectedAction === "poison" ? "border-purple-500 bg-purple-900/20" : "border-[var(--color-warm-border)] bg-[var(--color-warm-bg)]"}`}>
            <label className="flex items-center gap-2 cursor-pointer text-sm">
              <input type="radio" name="witch-action" checked={selectedAction === "poison"} onChange={() => setSelectedAction("poison")} />
              <span className="text-purple-400">使用毒药</span>
            </label>
            {selectedAction === "poison" && poisonTargets.length > 0 && (
              <div className="grid grid-cols-2 gap-1 mt-2 ml-5">
                {poisonTargets.map((target) => (
                  <label key={target.player_id} className={`flex items-center gap-1 p-1.5 rounded border cursor-pointer text-xs ${poisonTarget === target.player_id ? "border-purple-500 bg-purple-900/10" : "border-[var(--color-warm-border)]"}`}>
                    <input type="radio" name="poison-target" value={target.player_id} checked={poisonTarget === target.player_id} onChange={() => setPoisonTarget(target.player_id)} />
                    <span>{target.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {noAction && (
          <label className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer text-sm transition-colors ${selectedAction === "none" ? "border-[var(--color-gold)] bg-[var(--color-warm-card)]" : "border-[var(--color-warm-border)] bg-[var(--color-warm-bg)]"}`}>
            <input type="radio" name="witch-action" checked={selectedAction === "none"} onChange={() => setSelectedAction("none")} />
            <span>{noAction.label}</span>
          </label>
        )}
      </div>

      <DockButton disabled={pending} onClick={handleSubmit}>
        {selectedAction === "save" ? "使用解药" : selectedAction === "poison" ? "使用毒药" : "不使用药"}
      </DockButton>
    </DockWrapper>
  );
}

/* ── Shared primitives ── */

function DockWrapper({ children, night }: { children: React.ReactNode; night?: boolean }) {
  return (
    <motion.section
      className={`relative z-20 shrink-0 p-4 rounded-xl border ${night ? "border-[var(--color-blue-night)]/30 bg-[var(--color-warm-card)]" : "border-[var(--color-warm-border)] bg-[var(--color-warm-card)]"}`}
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div className="flex flex-col gap-3">{children}</div>
    </motion.section>
  );
}

function DockButton({ children, disabled, onClick }: { children: React.ReactNode; disabled: boolean; onClick: () => void }) {
  return (
    <button
      className="px-5 py-2.5 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold text-sm hover:bg-[var(--color-gold-dim)] disabled:opacity-50 transition-colors"
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function QuickTemplate({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      className="text-xs px-2.5 py-1 rounded border border-[var(--color-warm-border)] text-[var(--color-text-dim)] hover:border-[var(--color-gold)] hover:text-[var(--color-text)] transition-colors"
      onClick={onClick}
    >
      {label}
    </button>
  );
}
