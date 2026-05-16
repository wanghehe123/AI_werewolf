export interface QueueItem {
  playerId: string;
  label: string;
  audioData?: ArrayBuffer;
  fallbackText?: string;
  announcementId?: string;
  kind?: "system" | "speech";
}

export interface QueuePlayer {
  isPlaying: boolean;
  play(item: QueueItem): Promise<void>;
  stop(): void;
}

export class AudioQueue {
  private player: QueuePlayer;
  private queue: QueueItem[] = [];
  private currentItem: QueueItem | null = null;
  private enabled = true;
  private _onItemStart: ((item: QueueItem) => void) | null = null;
  private _onItemEnd: ((item: QueueItem) => void) | null = null;

  constructor(player: QueuePlayer) {
    this.player = player;
  }

  set onItemStart(callback: ((item: QueueItem) => void) | null) {
    this._onItemStart = callback;
  }

  set onItemEnd(callback: ((item: QueueItem) => void) | null) {
    this._onItemEnd = callback;
  }

  get isPlaying(): boolean {
    return this.currentItem !== null || this.player.isPlaying;
  }

  get currentPlayerId(): string | null {
    return this.currentItem?.playerId ?? null;
  }

  enqueue(item: QueueItem): void {
    this.queue.push(item);
    if (this.enabled && this.queue.length === 1 && !this.currentItem && !this.player.isPlaying) {
      this.playNext();
    }
  }

  clear(): void {
    this.player.stop();
    this.queue = [];
    this.currentItem = null;
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (enabled && this.queue.length > 0 && !this.currentItem && !this.player.isPlaying) {
      this.playNext();
    }
  }

  private playNext(): void {
    const item = this.queue.shift();
    if (!item) {
      this.currentItem = null;
      return;
    }

    this.currentItem = item;
    this._onItemStart?.(item);

    this.player.play(item).then(() => {
      this._onItemEnd?.(item!);
      this.currentItem = null;
      if (this.enabled) {
        setTimeout(() => this.playNext(), 0);
      }
    }).catch(() => {
      this.currentItem = null;
      if (this.enabled) {
        setTimeout(() => this.playNext(), 0);
      }
    });
  }

  destroy(): void {
    this.clear();
    this._onItemStart = null;
    this._onItemEnd = null;
  }
}
