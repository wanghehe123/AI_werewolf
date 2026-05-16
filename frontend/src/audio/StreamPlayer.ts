export class StreamPlayer {
  private audioContext: AudioContext | null = null;
  private sourceNode: AudioBufferSourceNode | null = null;
  private _onEnded: (() => void) | null = null;

  get isPlaying(): boolean {
    return this.sourceNode !== null;
  }

  set onEnded(callback: (() => void) | null) {
    this._onEnded = callback;
  }

  private ensureContext(): AudioContext {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }
    if (this.audioContext.state === "suspended") {
      this.audioContext.resume();
    }
    return this.audioContext;
  }

  async play(audioData: ArrayBuffer): Promise<void> {
    this.stop();
    const ctx = this.ensureContext();

    try {
      const audioBuffer = await ctx.decodeAudioData(audioData.slice(0));
      this.sourceNode = ctx.createBufferSource();
      this.sourceNode.buffer = audioBuffer;
      this.sourceNode.connect(ctx.destination);

      this.sourceNode.onended = () => {
        this.sourceNode = null;
        this._onEnded?.();
      };

      this.sourceNode.start(0);
    } catch (error) {
      this.sourceNode = null;
      throw error;
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

  setVolume(volume: number): void {
    if (this.audioContext) {
      const gainNode = (this.audioContext as Record<string, unknown>).__gainNode as GainNode | undefined;
      if (gainNode) {
        gainNode.gain.value = Math.max(0, Math.min(1, volume));
      }
    }
  }

  destroy(): void {
    this.stop();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}
