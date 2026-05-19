import { onUnmounted, ref } from 'vue'

export type RecorderState = 'idle' | 'recording' | 'recorded'

export function useAudioRecorder() {
  const state = ref<RecorderState>('idle')
  const durationSec = ref(0)
  const error = ref<string | null>(null)
  const blob = ref<Blob | null>(null)
  const base64 = ref<string | null>(null)
  const mimeType = ref('audio/webm')

  let mediaRecorder: MediaRecorder | null = null
  let chunks: BlobPart[] = []
  let timer: ReturnType<typeof setInterval> | null = null
  let stream: MediaStream | null = null

  const blobToBase64 = (b: Blob) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = reader.result as string
        resolve(result.split(',')[1] || '')
      }
      reader.onerror = reject
      reader.readAsDataURL(b)
    })

  const start = async () => {
    error.value = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const preferred = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      mediaRecorder = new MediaRecorder(stream, { mimeType: preferred })
      mimeType.value = preferred.split(';')[0]
      chunks = []
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data)
      }
      mediaRecorder.onstop = async () => {
        const recorded = new Blob(chunks, { type: mimeType.value })
        blob.value = recorded
        base64.value = await blobToBase64(recorded)
        state.value = 'recorded'
        stopTracks()
      }
      mediaRecorder.start()
      state.value = 'recording'
      durationSec.value = 0
      timer = setInterval(() => {
        durationSec.value += 1
      }, 1000)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '无法访问麦克风'
      state.value = 'idle'
    }
  }

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop()
    } else {
      stopTracks()
    }
  }

  const reset = () => {
    stopTracks()
    if (timer) clearInterval(timer)
    state.value = 'idle'
    durationSec.value = 0
    blob.value = null
    base64.value = null
    error.value = null
    chunks = []
  }

  const stopTracks = () => {
    stream?.getTracks().forEach((t) => t.stop())
    stream = null
  }

  const formatFromMime = () => {
    if (mimeType.value.includes('webm')) return 'webm'
    if (mimeType.value.includes('wav')) return 'wav'
    return 'webm'
  }

  onUnmounted(reset)

  return {
    state,
    durationSec,
    error,
    blob,
    base64,
    mimeType,
    start,
    stop,
    reset,
    formatFromMime,
  }
}
