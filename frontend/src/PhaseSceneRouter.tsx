import { useEffect, useMemo, useState } from "react";

import type { GameStateDto, PlayerActionOptionDto, SubmitActionInput } from "./types";

interface PhaseSceneRouterProps {
  game: GameStateDto;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
  pending: boolean;
}

export function PhaseSceneRouter({ game, onSubmitAction, pending }: PhaseSceneRouterProps) {
  const aliveTargets = useMemo(() => game.players.filter((player) => player.alive && !player.is_human), [game.players]);
  const primaryAction = game.allowed_actions[0];
  const nightTargetOptions = useMemo(() => primaryAction?.target_options ?? [], [primaryAction]);
  const [speech, setSpeech] = useState("我先听发言，今天重点看谁的逻辑变化。");
  const [voteTarget, setVoteTarget] = useState(aliveTargets[0]?.player_id ?? "");
  const [nightTarget, setNightTarget] = useState(nightTargetOptions[0]?.player_id ?? "");

  const humanPlayer = game.players.find((p) => p.player_id === game.human_player_id);
  const isAlive = humanPlayer?.alive ?? true;

  useEffect(() => {
    setNightTarget(nightTargetOptions[0]?.player_id ?? "");
  }, [primaryAction?.action_type, nightTargetOptions]);

  useEffect(() => {
    if (!aliveTargets.some((player) => player.player_id === voteTarget)) {
      setVoteTarget(aliveTargets[0]?.player_id ?? "");
    }
  }, [aliveTargets, voteTarget]);

  if (game.phase === "setup") {
    return (
      <section className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
        <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">SETUP</p>
        <h2>准备开局</h2>
        <p>座位和身份已由后端分配。点击开始后，房间进入第一夜。</p>
        <button className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50" disabled={pending} onClick={() => onSubmitAction({ action_type: "start_game" })}>
          开始游戏
        </button>
      </section>
    );
  }

  if (game.phase === "night") {
    if (!primaryAction) {
      return <ObserverScene kicker="NIGHT" title="夜晚行动" message={isAlive ? "等待其他玩家行动中..." : "你已出局，正在等待夜晚结算。"} />;
    }

    // Witch two-step night: step 1 — trigger wolf/seer/guard
    if (primaryAction.action_type === "night_start") {
      return (
        <section className="p-6 rounded-xl border border-[var(--color-blue-night)] bg-[var(--color-warm-card)]">
          <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">NIGHT</p>
          <h2>夜晚行动</h2>
          <p>你是女巫。夜晚降临，其他角色即将行动。</p>
          <p className="text-sm text-[var(--color-text-dim)] mt-2">点击按钮开始夜晚，你将在得知刀口后决定是否使用解药或毒药。</p>
          <button
            className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50"
            disabled={pending}
            onClick={() => onSubmitAction({ action_type: "night_start" })}
          >
            开始夜晚
          </button>
        </section>
      );
    }

    // Witch two-step night: step 2 — show kill info + save/poison/no_action
    if (primaryAction.night_kill_info) {
      return (
        <WitchNightAction
          actions={game.allowed_actions}
          killInfo={primaryAction.night_kill_info}
          pending={pending}
          onSubmitAction={onSubmitAction}
        />
      );
    }

    if (primaryAction?.requires_target) {
      return (
        <section className="p-6 rounded-xl border border-[var(--color-blue-night)] bg-[var(--color-warm-card)]">
          <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">NIGHT</p>
          <h2>夜晚行动</h2>
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label={primaryAction.label}>
            {nightTargetOptions.map((target) => (
              <label key={target.player_id} className="flex items-center gap-2 p-3 rounded-lg border border-[var(--color-warm-border)] hover:border-[var(--color-gold)] bg-[var(--color-warm-bg)] cursor-pointer">
                <input
                  type="radio"
                  name="night-target"
                  value={target.player_id}
                  checked={nightTarget === target.player_id}
                  onChange={() => setNightTarget(target.player_id)}
                />
                <span>{target.label}</span>
              </label>
            ))}
          </div>
          <button
            className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50"
            disabled={pending || !nightTarget}
            onClick={() => onSubmitAction({ action_type: primaryAction.action_type, target_player_id: nightTarget })}
          >
            {primaryAction.label}
          </button>
        </section>
      );
    }

    return (
      <section className="p-6 rounded-xl border border-[var(--color-blue-night)] bg-[var(--color-warm-card)]">
        <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">NIGHT</p>
        <h2>夜晚行动</h2>
        <p>你当前没有主动夜间技能，确认后等待夜晚结算。</p>
        <button className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50" disabled={pending} onClick={() => onSubmitAction({ action_type: primaryAction?.action_type ?? "skip" })}>
          {primaryAction?.label ?? "确认夜晚行动"}
        </button>
      </section>
    );
  }

  if (game.phase === "day_announcement") {
    return (
      <section className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
        <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">DAWN</p>
        <h2>昨夜信息</h2>
        <p>{lastMessage(game) ?? "天亮了，所有玩家睁眼。"}</p>
        <button className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50" disabled={pending} onClick={() => onSubmitAction({ action_type: "continue" })}>
          进入白天发言
        </button>
      </section>
    );
  }

  if (game.phase === "day_speech") {
    if (primaryAction?.action_type !== "speech") {
      return <ObserverScene kicker="SPEECH" title="白天发言" message={isAlive ? "等待其他玩家发言中..." : "你已出局，正在旁听其他玩家发言。"} />;
    }

    return (
      <section className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
        <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">SPEECH</p>
        <h2>白天发言</h2>
        <textarea
          aria-label="发言内容"
          className="w-full p-3 rounded-lg border border-[var(--color-warm-border)] bg-[var(--color-warm-bg)] text-[var(--color-text)] resize-y min-h-[100px]"
          value={speech}
          onChange={(event) => setSpeech(event.target.value)}
          rows={4}
        />
        <button className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50" disabled={pending || speech.trim().length === 0} onClick={() => onSubmitAction({ action_type: "speech", content: speech })}>
          提交发言
        </button>
      </section>
    );
  }

  if (game.phase === "exile_vote") {
    const canVote = game.allowed_actions.some((action) => action.action_type === "vote");
    const canAbstain = game.allowed_actions.some((action) => action.action_type === "abstain");
    if (!canVote && !canAbstain) {
      return <ObserverScene kicker="VOTE" title="放逐投票" message={isAlive ? "等待其他玩家投票中..." : "你已出局，正在等待其他玩家投票。"} />;
    }

    return (
      <section className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
        <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">VOTE</p>
        <h2>放逐投票</h2>
        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="投票目标">
          {aliveTargets.map((player) => (
            <label key={player.player_id} className="flex items-center gap-2 p-3 rounded-lg border border-[var(--color-warm-border)] hover:border-[var(--color-gold)] bg-[var(--color-warm-bg)] cursor-pointer">
              <input
                type="radio"
                name="vote-target"
                value={player.player_id}
                checked={voteTarget === player.player_id}
                onChange={() => setVoteTarget(player.player_id)}
              />
              <span>{player.seat}号 {player.display_name}</span>
            </label>
          ))}
        </div>
        <div className="flex gap-3">
          <button className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50" disabled={pending || !voteTarget || !canVote} onClick={() => onSubmitAction({ action_type: "vote", target_player_id: voteTarget })}>
            投票
          </button>
          <button className="px-6 py-3 rounded-lg border border-[var(--color-warm-border)] bg-transparent text-[var(--color-text)] font-semibold hover:bg-[var(--color-warm-card)] disabled:opacity-50" disabled={pending || !canAbstain} onClick={() => onSubmitAction({ action_type: "abstain" })}>
            弃票
          </button>
        </div>
      </section>
    );
  }

  if (game.phase === "last_words") {
    return (
      <section className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
        <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">LAST WORDS</p>
        <h2>遗言</h2>
        <p>{lastMessage(game) ?? "出局玩家留下遗言，随后进入下一阶段。"}</p>
        <button className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50" disabled={pending} onClick={() => onSubmitAction({ action_type: "continue" })}>
          继续
        </button>
      </section>
    );
  }

  return (
    <section className="p-6 rounded-xl border border-[var(--color-gold)] bg-[var(--color-warm-card)]">
      <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">REPLAY</p>
      <h2>游戏复盘</h2>
      <p>胜利阵营：{game.winner === "wolves" ? "狼人阵营" : "好人阵营"}</p>
      <div className="grid grid-cols-2 gap-2 mt-4">
        {game.players.map((player) => (
          <span key={player.player_id}>
            {player.seat}号 {player.display_name}：{player.role_key ?? "未知"}
          </span>
        ))}
      </div>
      <a className="px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] no-underline text-center inline-block" href="/">返回大厅</a>
    </section>
  );
}

/* ── Witch Night Action (separate component to use hooks safely) ── */

function WitchNightAction({
  actions,
  killInfo,
  pending,
  onSubmitAction,
}: {
  actions: PlayerActionOptionDto[];
  killInfo: NonNullable<PlayerActionOptionDto["night_kill_info"]>;
  pending: boolean;
  onSubmitAction: (action: SubmitActionInput) => Promise<void>;
}) {
  const saveAction = actions.find((a) => a.action_type === "witch_save");
  const poisonAction = actions.find((a) => a.action_type === "witch_poison");
  const noAction = actions.find((a) => a.action_type === "no_action");
  const poisonTargets = poisonAction?.target_options ?? [];

  const [selectedAction, setSelectedAction] = useState<string>(
    saveAction && killInfo.can_save ? "none" : "none",
  );
  const [poisonTarget, setPoisonTarget] = useState(poisonTargets[0]?.player_id ?? "");

  const handleSubmit = () => {
    if (selectedAction === "save" && saveAction) {
      onSubmitAction({ action_type: "witch_save", target_player_id: killInfo.target_id });
    } else if (selectedAction === "poison" && poisonTarget) {
      onSubmitAction({ action_type: "witch_poison", target_player_id: poisonTarget });
    } else {
      onSubmitAction({ action_type: "no_action" });
    }
  };

  return (
    <section className="p-6 rounded-xl border border-[var(--color-blue-night)] bg-[var(--color-warm-card)]">
      <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">NIGHT — 女巫</p>
      <h2>夜晚行动</h2>

      {/* Kill info banner */}
      <div className="p-4 rounded-lg bg-red-900/20 border border-red-800/40 mb-4">
        <p className="font-semibold text-red-300">
          今晚 {killInfo.target_label} 被狼人击杀。
        </p>
        {!killInfo.can_save && killInfo.reason && (
          <p className="text-sm text-red-400 mt-1">{killInfo.reason}</p>
        )}
      </div>

      <div className="space-y-3">
        {/* Save option */}
        {saveAction && killInfo.can_save && (
          <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedAction === "save" ? "border-green-500 bg-green-900/20" : "border-[var(--color-warm-border)] hover:border-[var(--color-gold)] bg-[var(--color-warm-bg)]"}`}>
            <input type="radio" name="witch-action" checked={selectedAction === "save"} onChange={() => setSelectedAction("save")} />
            <span className="text-green-400">使用解药救活 {killInfo.target_label}</span>
          </label>
        )}

        {/* Poison option */}
        {poisonAction && (
          <div className={`p-3 rounded-lg border transition-colors ${selectedAction === "poison" ? "border-purple-500 bg-purple-900/20" : "border-[var(--color-warm-border)] bg-[var(--color-warm-bg)]"}`}>
            <label className="flex items-center gap-3 cursor-pointer">
              <input type="radio" name="witch-action" checked={selectedAction === "poison"} onChange={() => setSelectedAction("poison")} />
              <span className="text-purple-400">使用毒药</span>
            </label>
            {selectedAction === "poison" && poisonTargets.length > 0 && (
              <div className="grid grid-cols-2 gap-2 mt-2 ml-6">
                {poisonTargets.map((target) => (
                  <label key={target.player_id} className={`flex items-center gap-2 p-2 rounded-md border cursor-pointer text-sm ${poisonTarget === target.player_id ? "border-purple-500 bg-purple-900/10" : "border-[var(--color-warm-border)]"}`}>
                    <input type="radio" name="poison-target" value={target.player_id} checked={poisonTarget === target.player_id} onChange={() => setPoisonTarget(target.player_id)} />
                    <span>{target.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {/* No action option */}
        {noAction && (
          <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${selectedAction === "none" ? "border-[var(--color-gold)] bg-[var(--color-warm-card)]" : "border-[var(--color-warm-border)] hover:border-[var(--color-gold)] bg-[var(--color-warm-bg)]"}`}>
            <input type="radio" name="witch-action" checked={selectedAction === "none"} onChange={() => setSelectedAction("none")} />
            <span>{noAction.label}</span>
          </label>
        )}
      </div>

      <button
        className="mt-4 px-6 py-3 rounded-lg bg-[var(--color-gold)] text-[var(--color-warm-bg)] font-semibold hover:bg-[var(--color-gold-dim)] disabled:opacity-50"
        disabled={pending}
        onClick={handleSubmit}
      >
        {selectedAction === "save" ? "使用解药" : selectedAction === "poison" ? "使用毒药" : "不使用药"}
      </button>
    </section>
  );
}

/* ── Shared helpers ── */

function ObserverScene({ kicker, title, message }: { kicker: string; title: string; message: string }) {
  return (
    <section className="p-6 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)]">
      <p className="text-xs tracking-[0.2em] uppercase text-[var(--color-text-dim)] mb-2">{kicker}</p>
      <h2>{title}</h2>
      <p>{message}</p>
    </section>
  );
}

function lastMessage(game: GameStateDto): string | undefined {
  return game.public_events.at(-1)?.payload.message;
}
