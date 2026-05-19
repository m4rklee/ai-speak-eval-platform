/** 批量/语音评测：将 outputAudio JSON 转为可播放 URL */

export type ParsedOutputAudio = {
  format: string
  data: string
}

const BLOB_URL_PREFIX = 'blob:'

export function parseOutputAudio(raw?: string | null): ParsedOutputAudio | null {
  if (!raw?.trim()) return null
  try {
    const obj = JSON.parse(raw) as { format?: string; data?: string }
    if (!obj?.data) return null
    return { format: (obj.format || 'wav').toLowerCase(), data: obj.data }
  } catch {
    return null
  }
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
}

/** OpenRouter gpt-audio 默认 pcm16 @ 24kHz mono */
export function pcm16Base64ToWavBytes(base64Pcm: string, sampleRate = 24000): Uint8Array {
  const binary = atob(base64Pcm)
  const pcm = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) pcm[i] = binary.charCodeAt(i)

  const numChannels = 1
  const bitsPerSample = 16
  const byteRate = sampleRate * numChannels * (bitsPerSample / 8)
  const blockAlign = numChannels * (bitsPerSample / 8)
  const dataSize = pcm.byteLength
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, byteRate, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitsPerSample, true)
  writeString(view, 36, 'data')
  view.setUint32(40, dataSize, true)
  new Uint8Array(buffer, 44).set(pcm)
  return new Uint8Array(buffer)
}

const MIME: Record<string, string> = {
  wav: 'audio/wav',
  mp3: 'audio/mpeg',
  webm: 'audio/webm',
  m4a: 'audio/mp4',
  ogg: 'audio/ogg',
}

/** 返回 blob: URL（调用方需在不用时 revoke）或 data: URL */
export function buildAudioPlaybackUrl(
  format: string,
  base64Data: string,
): { url: string; downloadExt: string; revoke?: () => void } {
  const fmt = format.toLowerCase()
  if (fmt === 'pcm16' || fmt === 'pcm') {
    const wavBytes = pcm16Base64ToWavBytes(base64Data)
    const blob = new Blob([wavBytes], { type: 'audio/wav' })
    const url = URL.createObjectURL(blob)
    return { url, downloadExt: 'wav', revoke: () => URL.revokeObjectURL(url) }
  }
  const mime = MIME[fmt] || `audio/${fmt}`
  return {
    url: `data:${mime};base64,${base64Data}`,
    downloadExt: fmt,
  }
}

export function revokePlaybackUrl(url: string) {
  if (url.startsWith(BLOB_URL_PREFIX)) URL.revokeObjectURL(url)
}
