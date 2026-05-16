import { describe, expect, it } from "vitest";

import { phaseToBgmTrack } from "./bgm";

describe("phaseToBgmTrack", () => {
  it("uses night BGM for night phase", () => {
    expect(phaseToBgmTrack("night")).toBe("night");
  });

  it("uses daytime BGM for active daytime phases", () => {
    expect(phaseToBgmTrack("day_announcement")).toBe("day");
    expect(phaseToBgmTrack("day_speech")).toBe("day");
    expect(phaseToBgmTrack("exile_vote")).toBe("day");
    expect(phaseToBgmTrack("last_words")).toBe("day");
  });

  it("does not play BGM before the game starts or after it ends", () => {
    expect(phaseToBgmTrack("setup")).toBeNull();
    expect(phaseToBgmTrack("game_over")).toBeNull();
  });
});
