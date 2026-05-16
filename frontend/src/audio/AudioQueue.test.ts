import { describe, expect, it, vi } from "vitest";
import { AudioQueue, type QueueItem } from "./AudioQueue";

describe("AudioQueue", () => {
  it("waits for the current audio playback promise before starting the next item", async () => {
    let finishFirst!: () => void;
    const player = {
      isPlaying: false,
      play: vi.fn((item: QueueItem) => {
        player.isPlaying = true;
        if (item.announcementId === "first") {
          return new Promise<void>((resolve) => {
            finishFirst = () => {
              player.isPlaying = false;
              resolve();
            };
          });
        }
        player.isPlaying = false;
        return Promise.resolve();
      }),
      stop: vi.fn(),
    };
    const queue = new AudioQueue(player);

    queue.enqueue({ playerId: "p1", label: "1号", announcementId: "first", audioData: new ArrayBuffer(1) });
    queue.enqueue({ playerId: "p2", label: "2号", announcementId: "second", audioData: new ArrayBuffer(1) });

    expect(player.play).toHaveBeenCalledTimes(1);
    expect(player.play.mock.calls[0][0].announcementId).toBe("first");

    finishFirst();
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(player.play).toHaveBeenCalledTimes(2);
    expect(player.play.mock.calls[1][0].announcementId).toBe("second");
  });

  it("does not start another item while a non-WebAudio fallback is still pending", async () => {
    let finishFirst!: () => void;
    const player = {
      isPlaying: false,
      play: vi.fn((item: QueueItem) => {
        if (item.announcementId === "first") {
          return new Promise<void>((resolve) => {
            finishFirst = resolve;
          });
        }
        return Promise.resolve();
      }),
      stop: vi.fn(),
    };
    const queue = new AudioQueue(player);

    queue.enqueue({ playerId: "p1", label: "1号", announcementId: "first", fallbackText: "第一条" });
    queue.enqueue({ playerId: "p2", label: "2号", announcementId: "second", fallbackText: "第二条" });

    expect(player.play).toHaveBeenCalledTimes(1);
    expect(queue.isPlaying).toBe(true);

    finishFirst();
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(player.play).toHaveBeenCalledTimes(2);
  });
});
