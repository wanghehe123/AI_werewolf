import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { buildVisualEvents, eventLabel, eventMessage } from "./gameVisuals";
import type { GameEventDto } from "../types";
import type { EventFilterKind, VisualEventItem } from "./gameVisualTypes";

interface EventRailProps {
  events: GameEventDto[];
  streamingSpeeches?: Array<{ label: string; speech: string }>;
  maxVisible?: number;
}

const FILTER_OPTIONS: { kind: EventFilterKind; label: string }[] = [
  { kind: "all", label: "全部" },
  { kind: "speech", label: "发言" },
  { kind: "action", label: "行动" },
];

export function EventRail({ events, streamingSpeeches = [], maxVisible = 20 }: EventRailProps) {
  const [filter, setFilter] = useState<EventFilterKind>("all");
  const [expanded, setExpanded] = useState(false);

  const visualEvents = buildVisualEvents(events);
  const filtered = filter === "all"
    ? visualEvents
    : visualEvents.filter((e) => e.filter === filter || e.filter === "all");

  const latestEvent = filtered[filtered.length - 1];
  const historicalEvents = filtered.slice(0, -1);
  const visibleHistorical = expanded
    ? historicalEvents
    : historicalEvents.slice(-maxVisible);

  return (
    <aside
      className="flex flex-col gap-2 p-4 rounded-xl border border-[var(--color-warm-border)] bg-[var(--color-warm-card)] h-full overflow-y-auto"
      aria-label="事件叙事轨"
    >
      <div className="flex items-center justify-between pb-2 border-b border-[var(--color-warm-border)]">
        <span className="text-sm font-semibold text-[var(--color-text-dim)]">事件叙事</span>
        <div className="flex gap-1">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.kind}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                filter === opt.kind
                  ? "bg-[var(--color-gold)] text-[var(--color-warm-bg)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
              onClick={() => setFilter(opt.kind)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Latest event - highlighted */}
      {latestEvent && (
        <div
          key={latestEvent.id}
          className="p-3 rounded-lg bg-[var(--color-warm-border)]/30 border border-[var(--color-gold)]/20"
        >
          <p className="text-xs font-semibold text-[var(--color-candle)] mb-1">{latestEvent.label}</p>
          <p className="text-sm">{latestEvent.message}</p>
        </div>
      )}

      {/* Historical events */}
      {visibleHistorical.length === 0 && !latestEvent && (
        <p className="text-sm text-[var(--color-text-muted)] italic">等待第一条事件。</p>
      )}

      {visibleHistorical.map((event) => (
        <div key={event.id} className="text-sm py-1">
          <span className="text-xs text-[var(--color-candle)] mr-2 font-medium">{event.label}</span>
          <span className="text-[var(--color-text-dim)]">{event.message}</span>
        </div>
      ))}

      {/* Streaming speeches */}
      {streamingSpeeches.map((speech, i) => (
        <motion.div
          className="text-sm text-[var(--color-gold)] max-h-[80px] overflow-y-auto rounded bg-[var(--color-gold)]/5 p-2"
          key={`streaming-${i}`}
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <span className="text-xs text-[var(--color-candle)] mr-1 font-medium">实时发言</span>
          <span className="font-medium">{speech.label}：</span>
          <span className="text-[var(--color-text-dim)]">{speech.speech}</span>
        </motion.div>
      ))}

      {/* Expand/collapse */}
      {historicalEvents.length > maxVisible && (
        <button
          className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] py-1"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "收起" : `展开全部 (${historicalEvents.length} 条)`}
        </button>
      )}
    </aside>
  );
}
