import { afterEach, describe, expect, it, vi } from "vitest";
import { StreamPlayer } from "./StreamPlayer";

describe("StreamPlayer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("falls back to browser speech synthesis when no audio data is available", async () => {
    const speak = vi.fn((utterance: SpeechSynthesisUtterance) => {
      utterance.onend?.({} as SpeechSynthesisEvent);
    });
    vi.stubGlobal("speechSynthesis", {
      cancel: vi.fn(),
      speak,
    });
    vi.stubGlobal("SpeechSynthesisUtterance", class {
      lang = "";
      rate = 1;
      pitch = 1;
      text: string;
      onend: ((event: SpeechSynthesisEvent) => void) | null = null;
      onerror: (() => void) | null = null;

      constructor(text: string) {
        this.text = text;
      }
    });

    const player = new StreamPlayer();

    await player.play({ playerId: "system", label: "系统播报", fallbackText: "天黑请闭眼" });

    expect(speak).toHaveBeenCalledTimes(1);
    const utterance = speak.mock.calls[0][0] as SpeechSynthesisUtterance;
    expect(utterance.text).toBe("天黑请闭眼");
    expect(utterance.lang).toBe("zh-CN");
  });
});
