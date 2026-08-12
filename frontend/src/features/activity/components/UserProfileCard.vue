<script setup lang="ts">
/** 用户信息卡：头像本地上传（居中裁剪缩放）+ 主标签 ID / 副标签签名就地编辑。 */

import { nextTick, ref } from 'vue'
import { Camera, PencilLine, UserRound } from 'lucide-vue-next'
import { NInput, NTooltip, useMessage } from 'naive-ui'
import { fileToAvatar, useProfile } from '@/features/activity/profile'

const { profile } = useProfile()
const message = useMessage()

const fileInput = ref<HTMLInputElement | null>(null)

function pickAvatar(): void {
  fileInput.value?.click()
}

async function onAvatarChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    profile.avatar = await fileToAvatar(file)
  } catch {
    message.error('头像读取失败，请换一张图片试试')
  }
}

/** 就地编辑：Enter / 失焦保存，Esc 取消 */
type EditableField = 'name' | 'signature'

const editing = ref<EditableField | null>(null)
const draft = ref('')
const editInput = ref<InstanceType<typeof NInput> | null>(null)

async function startEdit(field: EditableField): Promise<void> {
  draft.value = profile[field]
  editing.value = field
  await nextTick()
  editInput.value?.focus()
}

function commitEdit(): void {
  if (editing.value) profile[editing.value] = draft.value.trim()
  editing.value = null
}

function cancelEdit(): void {
  editing.value = null
}
</script>

<template>
  <section class="profile-card">
    <NTooltip :show-arrow="false">
      <template #trigger>
        <button type="button" class="avatar-btn" aria-label="更换头像" @click="pickAvatar">
          <img v-if="profile.avatar" class="avatar-img" :src="profile.avatar" alt="用户头像" />
          <span v-else-if="profile.name.trim()" class="avatar-fallback">
            {{ profile.name.trim().slice(0, 1).toUpperCase() }}
          </span>
          <UserRound v-else class="avatar-icon" :size="26" />
          <span class="avatar-mask"><Camera :size="15" /></span>
        </button>
      </template>
      点击更换头像
    </NTooltip>
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      class="avatar-input"
      @change="onAvatarChange"
    />

    <div class="profile-tags">
      <div class="tag-row">
        <NInput
          v-if="editing === 'name'"
          ref="editInput"
          v-model:value="draft"
          size="small"
          placeholder="输入 ID"
          @keyup.enter="commitEdit"
          @keyup.esc="cancelEdit"
          @blur="commitEdit"
        />
        <template v-else>
          <button
            type="button"
            class="tag-text tag-name"
            :class="{ unset: !profile.name }"
            @click="startEdit('name')"
          >
            {{ profile.name || '未设置 ID' }}
          </button>
          <button
            type="button"
            class="tag-edit"
            aria-label="编辑 ID"
            @click="startEdit('name')"
          >
            <PencilLine :size="12" />
          </button>
        </template>
      </div>
      <span class="tag-divider" aria-hidden="true"></span>
      <div class="tag-row">
        <NInput
          v-if="editing === 'signature'"
          ref="editInput"
          v-model:value="draft"
          size="small"
          placeholder="写一句签名"
          @keyup.enter="commitEdit"
          @keyup.esc="cancelEdit"
          @blur="commitEdit"
        />
        <template v-else>
          <button
            type="button"
            class="tag-text tag-signature"
            :class="{ unset: !profile.signature }"
            @click="startEdit('signature')"
          >
            {{ profile.signature || '还没有签名' }}
          </button>
          <button
            type="button"
            class="tag-edit"
            aria-label="编辑签名"
            @click="startEdit('signature')"
          >
            <PencilLine :size="12" />
          </button>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.profile-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 16px 16px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  flex: none;
}

.avatar-btn {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  flex: none;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--accent-soft);
  color: var(--accent-strong);
  cursor: pointer;
  overflow: hidden;
  transition: border-color 0.16s ease, transform 0.16s ease;
}

.avatar-btn:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 56px;
  font-weight: 700;
}

.avatar-icon {
  position: absolute;
  inset: 0;
  margin: auto;
  width: 56px;
  height: 56px;
  color: var(--faint);
}

.avatar-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(0 0 0 / 0.42);
  color: #ffffff;
  opacity: 0;
  transition: opacity 0.16s ease;
}

.avatar-btn:hover .avatar-mask {
  opacity: 1;
}

.avatar-input {
  display: none;
}

.profile-tags {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.tag-row {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  min-height: 24px;
}

.tag-text {
  min-width: 0;
  padding: 1px 0;
  border: 0;
  background: transparent;
  color: var(--text);
  text-align: center;
  cursor: text;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-name {
  font-size: 16px;
  font-weight: 700;
}

.tag-signature {
  font-size: 12px;
  color: var(--muted);
}

.tag-text.unset {
  color: var(--faint);
}

/* 主副标签间的主题色短粗分割线 */
.tag-divider {
  width: 36px;
  height: 4px;
  margin: 4px 0;
  border-radius: 99px;
  background: var(--accent);
  flex: none;
}

.tag-edit {
  position: absolute;
  right: -2px;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex: none;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--faint);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease, color 0.15s ease;
}

.tag-row:hover .tag-edit {
  opacity: 1;
}

.tag-edit:hover {
  color: var(--accent-strong);
}
</style>
