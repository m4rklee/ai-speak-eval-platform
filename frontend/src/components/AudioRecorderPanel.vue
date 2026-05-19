<template>
  <div class="audio-recorder-panel">
    <a-space direction="vertical" style="width: 100%">
      <a-space>
        <a-button
          v-if="recorder.state.value !== 'recording'"
          type="primary"
          :disabled="recorder.state.value === 'recorded' && !allowReRecord"
          @click="recorder.start()"
        >
          开始录制
        </a-button>
        <a-button v-else danger @click="recorder.stop()">停止录制</a-button>
        <a-button v-if="recorder.state.value === 'recorded'" @click="onReset">重新录制</a-button>
        <span v-if="recorder.state.value === 'recording'" class="rec-dot">录制中 {{ recorder.durationSec.value }}s</span>
      </a-space>
      <a-alert v-if="recorder.error.value" type="error" :message="recorder.error.value" show-icon />
      <audio
        v-if="previewUrl"
        controls
        :src="previewUrl"
        style="width: 100%; max-width: 400px"
      />
    </a-space>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useAudioRecorder } from '@/composables/useAudioRecorder'

const props = withDefaults(
  defineProps<{ allowReRecord?: boolean }>(),
  { allowReRecord: true }
)

const emit = defineEmits<{
  recorded: [payload: { data: string; format: string; name?: string }]
  cleared: []
}>()

const recorder = useAudioRecorder()

const previewUrl = computed(() => {
  if (!recorder.blob.value) return ''
  return URL.createObjectURL(recorder.blob.value)
})

watch(
  () => recorder.base64.value,
  (b64) => {
    if (b64 && recorder.state.value === 'recorded') {
      emit('recorded', {
        data: b64,
        format: recorder.formatFromMime(),
        name: `recording.${recorder.formatFromMime()}`,
      })
    }
  }
)

const onReset = () => {
  recorder.reset()
  emit('cleared')
}
</script>

<style scoped>
.rec-dot {
  color: #ff4d4f;
}
</style>
