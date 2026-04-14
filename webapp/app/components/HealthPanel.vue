<script setup lang="ts">
import type { DetailedHealthResponse, ApiError } from '../types/api'

interface HealthStatus extends DetailedHealthResponse {}

const toast = useToast()
const health = ref<HealthStatus | null>(null)
const isLoading = ref(false)

async function loadHealth() {
  try {
    isLoading.value = true
    health.value = await apiClient.health.getSystemStatus()
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || 'Không thể tải trạng thái hệ thống',
      color: 'red'
    })
  } finally {
    isLoading.value = false
  }
}

function getStatusColor(status: string) {
  return status === 'healthy' || status === 'connected' ? 'green' : 'red'
}

function getStatusIcon(status: string) {
  return status === 'healthy' || status === 'connected'
    ? 'i-lucide-check-circle'
    : 'i-lucide-x-circle'
}

onMounted(() => {
  loadHealth()
  // Auto refresh every 30 seconds
  setInterval(loadHealth, 30000)
})
</script>

<template>
  <div class="space-y-4">
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold">
            Trạng thái hệ thống
          </h3>
          <UButton
            icon="i-lucide-refresh-cw"
            size="sm"
            color="neutral"
            variant="ghost"
            :loading="isLoading"
            @click="loadHealth"
          >
            Làm mới
          </UButton>
        </div>
      </template>

      <div
        v-if="isLoading && !health"
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
        v-else-if="health"
        class="space-y-4"
      >
        <!-- Services -->
        <div>
          <h4 class="mb-3 font-semibold text-gray-900">
            Dịch vụ
          </h4>
          <div class="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            <div
              v-for="(check, name) in health.checks"
              :key="name"
              class="flex items-center gap-3 rounded-lg border border-gray-200 p-3"
            >
              <UIcon
                :name="getStatusIcon(check.status)"
                :class="`h-5 w-5 text-${getStatusColor(check.status)}-500`"
              />
              <div class="flex-1">
                <p class="font-medium text-gray-900">
                  {{ name }}
                </p>
                <p
                  class="text-sm"
                  :class="`text-${getStatusColor(check.status)}-600`"
                >
                  {{ check.status }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Database stats -->
        <div v-if="health.database">
          <h4 class="mb-3 font-semibold text-gray-900">
            Cơ sở dữ liệu
          </h4>
          <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div class="rounded-lg border border-gray-200 p-3">
              <p class="text-sm text-gray-500">
                Tổng tài liệu
              </p>
              <p class="text-2xl font-bold text-gray-900">
                {{ health.database.total_documents || 0 }}
              </p>
            </div>
            <div class="rounded-lg border border-gray-200 p-3">
              <p class="text-sm text-gray-500">
                Đang xử lý
              </p>
              <p class="text-2xl font-bold text-yellow-600">
                {{ health.database.processing || 0 }}
              </p>
            </div>
            <div class="rounded-lg border border-gray-200 p-3">
              <p class="text-sm text-gray-500">
                Thất bại
              </p>
              <p class="text-2xl font-bold text-red-600">
                {{ health.database.failed || 0 }}
              </p>
            </div>
          </div>
        </div>

        <!-- Vector store -->
        <div v-if="health.vector_store">
          <h4 class="mb-3 font-semibold text-gray-900">
            Vector Store
          </h4>
          <div class="rounded-lg border border-gray-200 p-3">
            <p class="text-sm text-gray-500">
              Tổng vectors
            </p>
            <p class="text-2xl font-bold text-gray-900">
              {{ health.vector_store.total_vectors || 0 }}
            </p>
          </div>
        </div>
      </div>

      <div
        v-else
        class="py-8 text-center text-gray-500"
      >
        Không thể tải thông tin sức khỏe
      </div>
    </UCard>
  </div>
</template>
