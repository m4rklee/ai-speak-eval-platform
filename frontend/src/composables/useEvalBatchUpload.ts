import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import type { UploadProps } from 'ant-design-vue'

export type EvalAcceptExt = 'wav' | 'txt'

function folderNameFromFileList(files: File[]): string {
  if (!files.length) return ''
  const rel = (files[0] as File & { webkitRelativePath?: string }).webkitRelativePath || ''
  const normalized = rel.replace(/\\/g, '/')
  const slash = normalized.indexOf('/')
  return slash > 0 ? normalized.slice(0, slash) : ''
}

export function useEvalBatchUpload(acceptExt: EvalAcceptExt) {
  const ext = acceptExt === 'wav' ? '.wav' : '.txt'
  const extLabel = acceptExt === 'wav' ? 'wav' : 'txt'

  const multiFiles = ref<File[]>([])
  const multiFileList = ref<UploadProps['fileList']>([])
  const dirFiles = ref<File[]>([])
  const dirFolderName = ref('')
  const zipFile = ref<File | null>(null)
  const dirInputRef = ref<HTMLInputElement | null>(null)

  const acceptMime = acceptExt === 'wav' ? '.wav,audio/wav' : '.txt,text/plain'

  function matchesExt(name: string) {
    return name.toLowerCase().endsWith(ext)
  }

  const onMultiBeforeUpload: UploadProps['beforeUpload'] = (file) => {
    const f = file as File
    if (!matchesExt(f.name)) {
      message.warning(`仅支持 ${extLabel}`)
      return false
    }
    multiFiles.value.push(f)
    multiFileList.value = [
      ...(multiFileList.value || []),
      { uid: `${Date.now()}-${f.name}`, name: f.name, status: 'done' },
    ]
    return false
  }

  const onMultiRemove: UploadProps['onRemove'] = (file) => {
    const name = file.name
    multiFiles.value = multiFiles.value.filter((f) => f.name !== name)
    multiFileList.value = (multiFileList.value || []).filter((f) => f.name !== name)
  }

  function pickDirectory() {
    dirInputRef.value?.click()
  }

  function onDirChange(e: Event) {
    const input = e.target as HTMLInputElement
    const list = input.files
    if (!list) return
    zipFile.value = null
    dirFiles.value = Array.from(list).filter((f) => matchesExt(f.name))
    dirFolderName.value = folderNameFromFileList(dirFiles.value)
    const folderLabel = dirFolderName.value ? `文件夹「${dirFolderName.value}」` : '文件夹'
    message.info(`已选择 ${folderLabel}，共 ${dirFiles.value.length} 个 ${extLabel}`)
    input.value = ''
  }

  const onZipBeforeUpload: UploadProps['beforeUpload'] = (file) => {
    zipFile.value = file as File
    dirFiles.value = []
    dirFolderName.value = ''
    return false
  }

  function clearBatch() {
    multiFiles.value = []
    multiFileList.value = []
    dirFiles.value = []
    dirFolderName.value = ''
    zipFile.value = null
  }

  function batchReady(mode: 'multi' | 'dir'): boolean {
    if (mode === 'multi') return multiFiles.value.length > 0
    return dirFiles.value.length > 0 || !!zipFile.value
  }

  function filesForSubmit(mode: 'multi' | 'dir'): { files: File[]; archive: File | null } {
    if (mode === 'multi') return { files: multiFiles.value, archive: null }
    return { files: dirFiles.value, archive: zipFile.value }
  }

  const dirSelectionHint = computed(() => {
    const n = dirFiles.value.length
    if (!n) return ''
    const name = dirFolderName.value
    return name ? `已选文件夹「${name}」· ${n} 个 ${extLabel}` : `已选 ${n} 个 ${extLabel}`
  })

  return {
    acceptMime,
    extLabel,
    multiFiles,
    multiFileList,
    dirFiles,
    dirFolderName,
    zipFile,
    dirInputRef,
    onMultiBeforeUpload,
    onMultiRemove,
    pickDirectory,
    onDirChange,
    onZipBeforeUpload,
    clearBatch,
    batchReady,
    filesForSubmit,
    dirSelectionHint,
  }
}
