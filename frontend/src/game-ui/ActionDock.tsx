import { useState, useEffect } from "react";
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
        <ActionSummary eyebrow="SHERIFF" title="警长竞选报名" />
        <p className="text-sm text-[var(--color-wolf-muted)]">
          这一轮先决定是否上警。候选人稍后会依次发言，其他人负责投票。
        </p>
        <div className="flex gap-3 justify-end">
          <DockButton
            disabled={pending || !canRun}
            onClick={() => onSubmitAction({ action_type: "run_for_sheriff" })}
          >
            参加竞选
          </DockButton>
          <button
            className="rounded-[18px] border border-[#dbe5fb] bg-white/70 px-5 py-3 text-sm font-bold text-[#526188] hover:bg-white disabled:opacity-50"
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
        <ActionSummary eyebrow="READY" title="座位和身份已由后端分配" detail="点击开始后，房间进入第一夜。" />
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
        <p className="text-sm font-bold text-[var(--color-wolf-muted)]">
          {isAlive ? "等待其他玩家行动中..." : "你已出局，正在旁观。"}
        </p>
      </DockWrapper>
    );
  }

  // ── Night: witch start ──
  if (actionKind === "night_start") {
    return (
      <DockWrapper night>
        <ActionSummary eyebrow="NIGHT" title="你是女巫" detail="夜晚降临，点击开始后决定是否使用药水。" />
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
        <ActionSummary eyebrow="NIGHT" title={primaryAction?.label ?? "夜晚行动"} />
        <p className="text-sm font-bold text-[var(--color-wolf-muted)]">
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
        <ActionSummary eyebrow="SPEECH" title={isSheriffSpeech ? "你正在竞选发言" : "你正在发言"} />
        <input
          aria-label="发言内容"
          className="min-h-[58px] flex-1 rounded-full border border-[#dbe5fb] bg-white/70 px-6 text-[#17213d] outline-none placeholder:text-[#9faed0] focus:border-[#8198ff] focus:bg-white"
          value={speech}
          onChange={(e) => setSpeech(e.target.value)}
          placeholder="输入你想说的话..."
        />
        <div className="flex gap-2">
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
          发送
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
        <ActionSummary eyebrow="VOTE" title={isSheriffVote ? "警长投票" : "放逐投票"} />
        <p className="text-sm font-bold text-[var(--color-wolf-muted)]">
          {targetPlayer
            ? `你将投给：${targetPlayer.seat}号 ${targetPlayer.display_name}`
            : `点击座位选择${isSheriffVote ? "警长候选人" : "投票目标"}`}
        </p>
        <div className="flex gap-3 justify-end">
          <DockButton disabled={pending || !selectedTargetId || !canVote} onClick={() => onSubmitAction({ action_type: "vote", target_player_id: selectedTargetId! })}>
            {isSheriffVote ? "投给他" : "投票"}
          </DockButton>
          <button
            className="rounded-[18px] border border-[#dbe5fb] bg-white/70 px-5 py-3 text-sm font-bold text-[#526188] hover:bg-white disabled:opacity-50"
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
      <ActionSummary eyebrow="NEXT" title={phaseLabel(game.phase)} detail={game.public_events.at(-1)?.payload.message ?? `${phaseLabel(game.phase)}阶段`} />
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
      <ActionSummary eyebrow="NIGHT — 女巫" title="夜晚行动" />

      {killInfo && (
        <div className="rounded-[18px] border border-[#ffd1d1] bg-[#fff0f0] p-3">
          <p className="text-sm font-semibold text-[#be3a45]">
            今晚 {killInfo.target_label} 被狼人击杀。
          </p>
          {!killInfo.can_save && killInfo.reason && (
            <p className="mt-1 text-xs text-[#be3a45]">{killInfo.reason}</p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {saveAction && killInfo?.can_save && (
          <label className={`flex cursor-pointer items-center gap-2 rounded-[18px] border px-4 py-3 text-sm font-bold transition-colors ${selectedAction === "save" ? "border-[#32c77a] bg-[#ecfff4] text-[#168552]" : "border-[#dbe5fb] bg-white/70 text-[#526188]"}`}>
            <input type="radio" name="witch-action" checked={selectedAction === "save"} onChange={() => setSelectedAction("save")} />
            <span>使用解药救活 {killInfo.target_label}</span>
          </label>
        )}

        {poisonAction && (
          <div className={`rounded-[18px] border px-4 py-3 transition-colors ${selectedAction === "poison" ? "border-[#8d77ff] bg-[#f0edff] text-[#6953d7]" : "border-[#dbe5fb] bg-white/70 text-[#526188]"}`}>
            <label className="flex cursor-pointer items-center gap-2 text-sm font-bold">
              <input type="radio" name="witch-action" checked={selectedAction === "poison"} onChange={() => setSelectedAction("poison")} />
              <span>使用毒药</span>
            </label>
            {selectedAction === "poison" && poisonTargets.length > 0 && (
              <div className="mt-2 grid grid-cols-2 gap-1">
                {poisonTargets.map((target) => (
                  <label key={target.player_id} className={`flex cursor-pointer items-center gap-1 rounded border p-1.5 text-xs ${poisonTarget === target.player_id ? "border-[#8d77ff] bg-white" : "border-[#dbe5fb]"}`}>
                    <input type="radio" name="poison-target" value={target.player_id} checked={poisonTarget === target.player_id} onChange={() => setPoisonTarget(target.player_id)} />
                    <span>{target.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {noAction && (
          <label className={`flex cursor-pointer items-center gap-2 rounded-[18px] border px-4 py-3 text-sm font-bold transition-colors ${selectedAction === "none" ? "border-[#8ba1ff] bg-[#eef3ff] text-[var(--color-wolf-blue)]" : "border-[#dbe5fb] bg-white/70 text-[#526188]"}`}>
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
      className={`wolf-glass relative z-20 shrink-0 rounded-[32px] px-7 py-5 ${night ? "ring-1 ring-[#97a8ff]/30" : ""}`}
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div className="flex items-center gap-4">{children}</div>
    </motion.section>
  );
}

function DockButton({ children, disabled, onClick }: { children: React.ReactNode; disabled: boolean; onClick: () => void }) {
  return (
    <button
      className="wolf-primary min-h-[52px] rounded-[20px] px-7 py-3 text-sm font-black transition disabled:opacity-50"
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
      className="rounded-full border border-[#dbe5fb] bg-white/60 px-3 py-1.5 text-xs font-bold text-[#6b7aa4] transition-colors hover:border-[#8ba1ff] hover:text-[var(--color-wolf-blue)]"
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function ActionSummary({ eyebrow, title, detail }: { eyebrow: string; title: string; detail?: string }) {
  return (
    <div className="min-w-[220px]">
      <p className="text-xs font-black uppercase tracking-[0.18em] text-[var(--color-wolf-blue)]">{eyebrow}</p>
      <h3 className="mt-1 text-base font-black text-[#17213d]">{title}</h3>
      {detail && <p className="mt-1 text-sm text-[var(--color-wolf-muted)]">{detail}</p>}
    </div>
  );
}
