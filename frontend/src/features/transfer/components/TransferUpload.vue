<script setup lang="ts">
import { ref } from 'vue'
import { FileArchive } from 'lucide-vue-next'
import { NIcon, NText, NUpload, NUploadDragger, type UploadFileInfo } from 'naive-ui'

defineProps<{
  loading?: boolean
  hint: string
}>()

const emit = defineEmits<{
  select: [file: File]
}>()

const fileList = ref<UploadFileInfo[]>([])

function onChange(options: { fileList: UploadFileInfo[] }): void {
  const info = options.fileList[options.fileList.length - 1]
  fileList.value = info ? [info] : []
  if (info?.file) emit('select', info.file)
}
</script>

<template>
  <n-upload
    v-model:file-list="fileList"
    :default-upload="false"
    accept=".zip,application/zip"
    :disabled="loading"
    @change="onChange"
  >
    <n-upload-dragger class="transfer-dropzone">
      <div class="transfer-dropzone-icon">
        <n-icon :size="26"><FileArchive /></n-icon>
      </div>
      <n-text class="transfer-dropzone-text">点击选择或拖拽 zip 压缩包到此处</n-text>
      <n-text depth="3" class="transfer-dropzone-hint">{{ hint }}</n-text>
    </n-upload-dragger>
  </n-upload>
</template>

<style scoped>
.transfer-dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px 16px;
}

.transfer-dropzone-icon {
  color: var(--accent);
}

.transfer-dropzone-text {
  font-size: 13px;
}

.transfer-dropzone-hint {
  font-size: 12px;
}
</style>
