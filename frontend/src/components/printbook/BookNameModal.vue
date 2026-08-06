<script setup lang="ts">
import { reactive, watch } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, useMessage } from 'naive-ui'

const props = defineProps<{
  show: boolean
  mode: 'create' | 'rename'
  initialName: string
  initialTitle: string
}>()

const emit = defineEmits<{
  'update:show': [show: boolean]
  submit: [name: string, title: string]
}>()

const message = useMessage()
const form = reactive({ name: '', title: '' })

watch(
  () => props.show,
  (show) => {
    if (show) {
      form.name = props.initialName
      form.title = props.initialTitle
    }
  },
)

function submit(): void {
  if (!form.name.trim()) {
    message.error('册名不能为空')
    return
  }
  emit('submit', form.name.trim(), form.title.trim())
  emit('update:show', false)
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    class="create-modal pb-name-modal"
    :title="mode === 'create' ? '新建打印册' : '重命名打印册'"
    :style="{ width: '420px' }"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top" size="small">
      <n-form-item label="册名">
        <n-input
          v-model:value="form.name"
          maxlength="40"
          placeholder="如 ICPC区域赛版"
        />
      </n-form-item>
      <!-- 封面标题由"封面与选项"统一维护，重命名时不再出现 -->
      <n-form-item v-if="mode === 'create'" label="封面标题">
        <n-input
          v-model:value="form.title"
          maxlength="40"
          placeholder="留空与册名一致"
        />
      </n-form-item>
    </n-form>
    <div class="modal-actions">
      <n-button size="small" quaternary @click="emit('update:show', false)">取消</n-button>
      <n-button size="small" type="primary" @click="submit">保存</n-button>
    </div>
  </n-modal>
</template>

<style scoped>
.pb-name-modal {
  --n-border-radius: 12px;
}
</style>
