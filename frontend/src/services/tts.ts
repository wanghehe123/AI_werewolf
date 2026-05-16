import { apiBaseUrl } from "../api";

export interface TtsRequest {
  text: string;
  voice?: string;
}

export async function fetchTtsAudio(
  gameId: string,
  request: TtsRequest,
  baseUrl = apiBaseUrl()
): Promise<ArrayBuffer> {
  const response = await fetch(`${baseUrl}/games/${gameId}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: request.text,
      voice: request.voice ?? "zh-CN-XiaoxiaoNeural"
    })
  });

  if (!response.ok) {
    throw new Error(`TTS request failed: ${response.status} ${response.statusText}`);
  }

  return response.arrayBuffer();
}

export const VOICE_MAP: Record<string, string> = {
  default: "zh-CN-XiaoxiaoNeural",
  deep: "zh-CN-YunxiNeural",
  bright: "zh-CN-XiaoyiNeural",
  calm: "zh-CN-YunjianNeural",
  gentle: "zh-CN-XiaochenNeural",
};

export function getVoiceForAgent(voicePreference?: string): string {
  return voicePreference && voicePreference in VOICE_MAP
    ? VOICE_MAP[voicePreference]
    : VOICE_MAP.default;
}
