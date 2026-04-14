<script setup lang="ts">
import type { DocumentSummaryResponse, ApiError } from '../types/api'

interface Document extends DocumentSummaryResponse {}

const toast = useToast()
const documents = ref<Document[]>([])
const isLoading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

async function loadDocuments() {
  try {
    isLoading.value = true
    const response = await apiClient.documents.list()
    // Backend returns {items: [...], total: number}
    documents.value = response.items || []
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || 'Không thể tải danh sách tài liệu',
      color: 'red'
    })
  } finally {
    isLoading.value = false
  }
}

async function uploadFile(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  try {
    isLoading.value = true
    await apiClient.documents.upload(file)

    toast.add({
      title: 'Thành công',
      description: 'Đang xử lý tài liệu...',
      color: 'green'
    })

    await loadDocuments()
  } catch (error) {
    toast.add({
      title: 'Lỗi',
      description: (error as ApiError).response?.data?.detail || 'Không thể tải lên',
      color: 'red'
    })
  } finally {
    isLoading.value = false
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

async function deleteDocument(documentId: string) {
  if (!confirm('Bạn có chắc chắn muốn xóa tài liệu này?')) return

  try {
    isLoading.value = true
    await apiClient.documents.delete(documentId)

    toast.add({
      title: 'Thành công',
      description: 'Đã xóa tài liệu',
      color: 'green'
    })

    await loadDocuments()
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || 'Không thể xóa tài liệu',
      color: 'red'
    })
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadDocuments()
})
</script>

<template>
  <div class="space-y-4">
    <!-- Upload -->
    <UCard>
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold">
            Tải lên tài liệu
          </h3>
          <p class="text-sm text-gray-500">
            Hỗ trợ PDF, DOCX, TXT
          </p>
        </div>
        <input
          ref="fileInput"
          type="file"
          class="hidden"
          accept=".pdf,.docx,.txt"
          @change="uploadFile"
        >
        <UButton
          icon="i-lucide-upload"
          :loading="isLoading"
          @click="fileInput?.click()"
        >
          Chọn file
        </UButton>
      </div>
    </UCard>

    <!-- Documents list -->
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold">
            Danh sách tài liệu
          </h3>
          <UButton
            icon="i-lucide-refresh-cw"
            size="sm"
            color="neutral"
            variant="ghost"
            :loading="isLoading"
            @click="loadDocuments"
          />
        </div>
      </template>

      <div
        v-if="isLoading && documents.length === 0"
        class="py-8 text-center"
      >
        <UIcon
          name="i-lucide-loader-2"
          class="mx-auto h-8 w-8 animate-spin text-gray-400"
        />
        <p class="mt-2 text-sm text-gray-500">
          Đang tải...
        </p>
      </div>

      <div
        v-else-if="documents.length === 0"
        class="py-8 text-center"
      >
        <p class="text-gray-500">
          Chưa có tài liệu nào
        </p>
      </div>

      <div
        v-else
        class="space-y-2"
      >
        <div
          v-for="doc in documents"
          :key="doc.document_id"
          class="flex items-center justify-between rounded-lg border border-gray-200 p-4"
        >
          <div class="flex-1">
            <p class="font-medium text-gray-900">
              {{ doc.file_name }}
            </p>
            <div class="mt-1 flex items-center gap-4 text-sm text-gray-500">
              <span>Trạng thái: {{ doc.status }}</span>
              <span>Kích thước: {{ (doc.file_size / 1024).toFixed(2) }} KB</span>
              <span v-if="doc.created_at">
                {{ new Date(doc.created_at).toLocaleDateString('vi-VN') }}
              </span>
            </div>
          </div>
          <UButton
            icon="i-lucide-trash-2"
            color="red"
            variant="ghost"
            size="sm"
            @click="deleteDocument(doc.document_id)"
          />
        </div>
      </div>
    </UCard>
  </div>
</template>
