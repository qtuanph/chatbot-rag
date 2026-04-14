<script setup lang="ts">
import type { DocumentSummaryResponse, ApiError } from '../types/api'

interface Document extends DocumentSummaryResponse {}

const router = useRouter()
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

function getStatusText(status: string, stage: string) {
  const statusMap: Record<string, string> = {
    'pending': '⏳ Chờ xử lý',
    'processing': `🔄 ${stage || 'Đang xử lý'}`,
    'ready': '✅ Hoàn thành',
    'failed': '❌ Thất bại'
  }
  return statusMap[status] || status
}

function getStatusColor(status: string) {
  const colorMap: Record<string, string> = {
    'pending': 'yellow',
    'processing': 'blue',
    'ready': 'green',
    'failed': 'red'
  }
  return colorMap[status] || 'gray'
}

function viewDetails(doc: Document) {
  const details = `
📄 THÔNG TIN TÀI LIỆU

• Tiêu đề: ${doc.title || doc.file_name}
• Trạng thái: ${getStatusText(doc.status, doc.stage)}
• Kích thước: ${(doc.file_size / 1024).toFixed(2)} KB
• Version: ${doc.version}
• Giai đoạn: ${doc.stage}
• Tiến độ: ${doc.progress_percent}%
• Ngày tạo: ${new Date(doc.created_at).toLocaleString('vi-VN')}
• Cập nhật: ${new Date(doc.updated_at).toLocaleString('vi-VN')}

📋 Document ID:
${doc.document_id}

${doc.status_message ? `ℹ️ Trạng thái: ${doc.status_message}` : ''}
  `
  alert(details)
}

function viewTree(documentId: string) {
  // Navigate to admin page with tree tab and document ID
  router.push({ path: '/admin', query: { tab: 'tree', doc: documentId } })
}

onMounted(() => {
  loadDocuments()
  // Auto-refresh every 3 seconds for processing documents
  const refreshInterval = setInterval(() => {
    const hasProcessing = documents.value.some(doc =>
      doc.status === 'processing' || doc.status === 'pending' || doc.progress_percent < 100
    )
    if (hasProcessing) {
      loadDocuments()
    }
  }, 3000)

  // Cleanup on unmount
  onUnmounted(() => {
    clearInterval(refreshInterval)
  })
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
        class="space-y-3"
      >
        <div
          v-for="doc in documents"
          :key="doc.document_id"
          class="rounded-lg border border-gray-200 bg-white p-4"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <!-- Title and status badge -->
              <div class="flex items-center gap-2">
                <h4 class="text-base font-semibold text-gray-900">
                  {{ doc.title || doc.file_name }}
                </h4>
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs font-medium"
                  :class="`bg-${getStatusColor(doc.status)}-100 text-${getStatusColor(doc.status)}-800`"
                >
                  {{ getStatusText(doc.status, doc.stage) }}
                </span>
              </div>

              <!-- Metadata -->
              <div class="mt-2 text-sm text-gray-600">
                <p>
                  📦 {{ (doc.file_size / 1024).toFixed(2) }} KB
                  <span class="mx-2">•</span>
                  📅 {{ new Date(doc.created_at).toLocaleDateString('vi-VN') }}
                  <span class="mx-2">•</span>
                  Version {{ doc.version }}
                </p>
              </div>

              <!-- Progress bar for processing documents -->
              <div v-if="doc.status === 'processing' || doc.progress_percent < 100" class="mt-3">
                <div class="flex items-center justify-between text-xs text-gray-600 mb-1">
                  <span>⏳ Tiến độ xử lý</span>
                  <span class="font-medium">{{ doc.progress_percent }}%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2.5">
                  <div
                    class="bg-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                    :style="{ width: doc.progress_percent + '%' }"
                  ></div>
                </div>
                <p v-if="doc.status_message" class="text-xs text-gray-500 mt-1.5">
                  💬 {{ doc.status_message }}
                </p>
              </div>
            </div>

            <!-- Action buttons -->
            <div class="flex flex-col gap-2 ml-4">
              <!-- View tree button (only for completed documents) -->
              <UButton
                v-if="doc.status === 'ready'"
                icon="i-lucide-network"
                color="green"
                variant="soft"
                size="xs"
                @click="viewTree(doc.document_id)"
              >
                Xem cây
              </UButton>

              <!-- View details button -->
              <UButton
                icon="i-lucide-info"
                color="blue"
                variant="soft"
                size="xs"
                @click="viewDetails(doc)"
              >
                Chi tiết
              </UButton>

              <!-- Delete button -->
              <UButton
                icon="i-lucide-trash-2"
                color="red"
                variant="soft"
                size="xs"
                @click="deleteDocument(doc.document_id)"
              >
                Xóa
              </UButton>
            </div>
          </div>
        </div>
      </div>
    </UCard>
  </div>
</template>
