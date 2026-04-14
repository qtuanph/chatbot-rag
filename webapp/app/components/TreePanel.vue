<script setup lang="ts">
import type { DocumentSummaryResponse, TreeDataResponse, TreeNode, ApiError } from '../types/api'

interface Document extends DocumentSummaryResponse {}

const toast = useToast()
const documents = ref<Document[]>([])
const selectedDocument = ref<string | null>(null)
const treeData = ref<TreeDataResponse | null>(null)
const searchQuery = ref('')
const isLoading = ref(false)

// Watch for route query params to auto-select document
const route = useRoute()
watch(() => route.query, (query) => {
  if (query.tab === 'tree' && query.doc) {
    const docId = query.doc as string
    if (docId && documents.value.some(d => d.document_id === docId)) {
      selectedDocument.value = docId
      loadTree()
    }
  }
}, { immediate: true })

async function loadDocuments() {
  try {
    isLoading.value = true
    const response = await apiClient.documents.list()
    documents.value = response.items.filter((d: Document) => d.status === 'completed')
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

async function loadTree() {
  if (!selectedDocument.value) return

  try {
    isLoading.value = true
    treeData.value = await apiClient.documents.getTree(selectedDocument.value)
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || 'Không thể tải cây tài liệu',
      color: 'red'
    })
  } finally {
    isLoading.value = false
  }
}

async function searchNodes() {
  if (!selectedDocument.value || !searchQuery.value) return

  try {
    isLoading.value = true
    const results = await apiClient.documents.searchNodes(
      selectedDocument.value,
      searchQuery.value
    )
    toast.add({
      title: 'Kết quả',
      description: `Tìm thấy ${results.nodes?.length || 0} kết quả`,
      color: 'green'
    })
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || 'Không thể tìm kiếm',
      color: 'red'
    })
  } finally {
    isLoading.value = false
  }
}

watch(selectedDocument, () => {
  if (selectedDocument.value) {
    loadTree()
  }
})

onMounted(() => {
  loadDocuments()
})
</script>

<template>
  <div class="space-y-4">
    <UCard>
      <h3 class="mb-4 text-lg font-semibold">
        Xem cây tài liệu
      </h3>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <USelect
          v-model="selectedDocument"
          placeholder="Chọn tài liệu"
          :items="documents.map(d => ({ label: d.file_name, value: d.document_id }))"
          :disabled="isLoading"
        />
        <UButton
          icon="i-lucide-search"
          :disabled="!selectedDocument"
          :loading="isLoading"
          @click="loadTree"
        >
          Xem cây
        </UButton>
      </div>
    </UCard>

    <UCard v-if="selectedDocument">
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold">
            Cây phân cấp
          </h3>
          <div class="flex items-center gap-2">
            <UInput
              v-model="searchQuery"
              placeholder="Tìm kiếm..."
              class="w-48"
              :disabled="isLoading"
            />
            <UButton
              icon="i-lucide-search"
              size="sm"
              :disabled="!searchQuery"
              :loading="isLoading"
              @click="searchNodes"
            />
          </div>
        </div>
      </template>

      <div
        v-if="isLoading"
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
        v-else-if="treeData"
        class="max-h-[600px] overflow-y-auto"
      >
        <div class="space-y-2">
          <TreeNode :node="treeData" />
        </div>
      </div>

      <div
        v-else
        class="py-8 text-center text-gray-500"
      >
        Chọn tài liệu để xem cấu trúc
      </div>
    </UCard>
  </div>
</template>
