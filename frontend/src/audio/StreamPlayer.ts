import type { QueueItem } from "./AudioQueue";

export class StreamPlayer {
  private audioContext: AudioContext | null = null;
  private sourceNode: AudioBufferSourceNode | null = null;

  get isPlaying(): boolean {
    return this.sourceNode !== null;
  }

  async unlock(): Promise<void> {
    if (typeof AudioContext === "undefined") return;
    const ctx = await this.ensureContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
  }

  private async ensureContext(): Promise<AudioContext> {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
    return this.audioContext;
  }

  async play(item: QueueItem): Promise<void> {
    if (!item.audioData || item.audioData.byteLength === 0) {
      await this.speakText(item.fallbackText ?? item.label);
      return;
    }

    this.stop();

    try {
      const ctx = await this.ensureContext();
      const audioBuffer = await ctx.decodeAudioData(item.audioData.slice(0));
      this.sourceNode = ctx.createBufferSource();
      this.sourceNode.buffer = audioBuffer;
      this.sourceNode.connect(ctx.destination);

      await new Promise<void>((resolve, reject) => {
        const source = this.sourceNode;
        if (!source) {
          reject(new Error("audio source was not created"));
          return;
        }
        source.onended = () => {
          if (this.sourceNode === source) {
            this.sourceNode = null;
          }
          resolve();
        };
        try {
          source.start(0);
        } catch (error) {
          this.sourceNode = null;
          reject(error);
        }
      });
    } catch (error) {
      this.sourceNode = null;
      await this.speakText(item.fallbackText ?? item.label);
    }
  }

  stop(): void {
    if (this.sourceNode) {
      try {
        this.sourceNode.stop(0);
      } catch {
        // Already stopped
      }
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
  }

  // Volume control not yet wired; reserved for future use

  destroy(): void {
    this.stop();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }

  private async speakText(text: string): Promise<void> {
    if (!text.trim() || typeof window === "undefined" || !window.speechSynthesis) {
      return;
    }

    await new Promise<void>((resolve) => {
      let resolved = false;
      const finish = () => {
        if (resolved) return;
        resolved = true;
        window.clearTimeout(timeoutId);
        resolve();
      };
      const timeoutMs = Math.min(Math.max(text.length * 260, 3000), 30000);
      const timeoutId = window.setTimeout(finish, timeoutMs);
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "zh-CN";
      utterance.rate = 1;
      utterance.pitch = 1;
      utterance.onend = finish;
      utterance.onerror = finish;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    });
  }
}
