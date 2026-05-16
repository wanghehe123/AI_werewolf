import { useEffect, useMemo, useState } from "react";

import type { GameStateDto, SubmitActionInput } from "./types";

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
      <section className="scene-panel">
        <p className="scene-kicker">SETUP</p>
        <h2>准备开局</h2>
        <p>座位和身份已由后端分配。点击开始后，房间进入第一夜。</p>
        <button className="primary-action" disabled={pending} onClick={() => onSubmitAction({ action_type: "start_game" })}>
          开始游戏
        </button>
      </section>
    );
  }

  if (game.phase === "night") {
    if (!primaryAction) {
      return <ObserverScene kicker="NIGHT" title="夜晚行动" message="你已出局，正在等待夜晚结算。" />;
    }

    if (primaryAction?.requires_target) {
      return (
        <section className="scene-panel night-scene">
          <p className="scene-kicker">NIGHT</p>
          <h2>夜晚行动</h2>
          <div className="target-grid" role="radiogroup" aria-label={primaryAction.label}>
            {nightTargetOptions.map((target) => (
              <label key={target.player_id} className="target-option">
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
            className="primary-action"
            disabled={pending || !nightTarget}
            onClick={() => onSubmitAction({ action_type: primaryAction.action_type, target_player_id: nightTarget })}
          >
            {primaryAction.label}
          </button>
        </section>
      );
    }

    return (
      <section className="scene-panel night-scene">
        <p className="scene-kicker">NIGHT</p>
        <h2>夜晚行动</h2>
        <p>你当前没有主动夜间技能，确认后等待夜晚结算。</p>
        <button className="primary-action" disabled={pending} onClick={() => onSubmitAction({ action_type: primaryAction?.action_type ?? "skip" })}>
          {primaryAction?.label ?? "确认夜晚行动"}
        </button>
      </section>
    );
  }

  if (game.phase === "day_announcement") {
    return (
      <section className="scene-panel">
        <p className="scene-kicker">DAWN</p>
        <h2>昨夜信息</h2>
        <p>{lastMessage(game) ?? "天亮了，所有玩家睁眼。"}</p>
        <button className="primary-action" disabled={pending} onClick={() => onSubmitAction({ action_type: "continue" })}>
          进入白天发言
        </button>
      </section>
    );
  }

  if (game.phase === "day_speech") {
    if (primaryAction?.action_type !== "speech") {
      return <ObserverScene kicker="SPEECH" title="白天发言" message="你已出局，正在旁听其他玩家发言。" />;
    }

    return (
      <section className="scene-panel">
        <p className="scene-kicker">SPEECH</p>
        <h2>白天发言</h2>
        <textarea
          aria-label="发言内容"
          className="speech-input"
          value={speech}
          onChange={(event) => setSpeech(event.target.value)}
          rows={4}
        />
        <button className="primary-action" disabled={pending || speech.trim().length === 0} onClick={() => onSubmitAction({ action_type: "speech", content: speech })}>
          提交发言
        </button>
      </section>
    );
  }

  if (game.phase === "exile_vote") {
    const canVote = game.allowed_actions.some((action) => action.action_type === "vote");
    const canAbstain = game.allowed_actions.some((action) => action.action_type === "abstain");
    if (!canVote && !canAbstain) {
      return <ObserverScene kicker="VOTE" title="放逐投票" message="你已出局，正在等待其他玩家投票。" />;
    }

    return (
      <section className="scene-panel">
        <p className="scene-kicker">VOTE</p>
        <h2>放逐投票</h2>
        <div className="target-grid" role="radiogroup" aria-label="投票目标">
          {aliveTargets.map((player) => (
            <label key={player.player_id} className="target-option">
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
        <div className="action-row">
          <button className="primary-action" disabled={pending || !voteTarget || !canVote} onClick={() => onSubmitAction({ action_type: "vote", target_player_id: voteTarget })}>
            投票
          </button>
          <button className="ghost-action" disabled={pending || !canAbstain} onClick={() => onSubmitAction({ action_type: "abstain" })}>
            弃票
          </button>
        </div>
      </section>
    );
  }

  if (game.phase === "last_words") {
    return (
      <section className="scene-panel">
        <p className="scene-kicker">LAST WORDS</p>
        <h2>遗言</h2>
        <p>{lastMessage(game) ?? "出局玩家留下遗言，随后进入下一阶段。"}</p>
        <button className="primary-action" disabled={pending} onClick={() => onSubmitAction({ action_type: "continue" })}>
          继续
        </button>
      </section>
    );
  }

  return (
    <section className="scene-panel result-scene">
      <p className="scene-kicker">REPLAY</p>
      <h2>游戏复盘</h2>
      <p>胜利阵营：{game.winner === "wolves" ? "狼人阵营" : "好人阵营"}</p>
      <div className="role-reveal">
        {game.players.map((player) => (
          <span key={player.player_id}>
            {player.seat}号 {player.display_name}：{player.role_key ?? "未知"}
          </span>
        ))}
      </div>
      <a className="primary-link" href="/">返回大厅</a>
    </section>
  );
}

function ObserverScene({ kicker, title, message }: { kicker: string; title: string; message: string }) {
  return (
    <section className="scene-panel">
      <p className="scene-kicker">{kicker}</p>
      <h2>{title}</h2>
      <p>{message}</p>
    </section>
  );
}

function lastMessage(game: GameStateDto): string | undefined {
  return game.public_events.at(-1)?.payload.message;
}
