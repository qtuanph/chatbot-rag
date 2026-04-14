<script setup lang="ts">
import type { TabsItem } from '@nuxt/ui'

const router = useRouter()
const toast = useToast()
const username = ref('')

// Check if admin
onMounted(() => {
  if (!apiClient.auth.isAuthenticated()) {
    router.push('/')
    return
  }

  // Get username from localStorage
  username.value = localStorage.getItem('username') || 'Admin'

  if (apiClient.auth.getUserRole() !== 'admin') {
    toast.add({
      title: 'Không có quyền truy cập',
      description: 'Trang này chỉ dành cho quản trị viên',
      color: 'red',
      icon: 'i-lucide-x-circle'
    })
    router.push('/chat')
  }
})

// Tab items
const items = computed<TabsItem[]>(() => [
  {
    label: 'Tài liệu',
    icon: 'i-lucide-file-text',
    slot: 'documents'
  },
  {
    label: 'Người dùng',
    icon: 'i-lucide-users',
    slot: 'users'
  },
  {
    label: 'Sức khỏe',
    icon: 'i-lucide-activity',
    slot: 'health'
  },
  {
    label: 'Cây tài liệu',
    icon: 'i-lucide-network',
    slot: 'tree'
  }
])

async function logout() {
  try {
    await apiClient.auth.logout()
    router.push('/')
  } catch {
    router.push('/')
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <div class="border-b border-gray-200 bg-white">
      <UContainer class="py-4">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-xl font-bold text-gray-900">
              Quản trị hệ thống
            </h1>
            <p class="text-sm text-gray-500">
              Chào mừng, {{ username }}
            </p>
          </div>
          <div class="flex items-center gap-2">
            <UButton
              to="/chat"
              icon="i-lucide-message-square"
              color="neutral"
              variant="ghost"
            >
              Chat
            </UButton>
            <UButton
              icon="i-lucide-log-out"
              color="neutral"
              variant="ghost"
              @click="logout"
            >
              Đăng xuất
            </UButton>
          </div>
        </div>
      </UContainer>
    </div>

    <!-- Content -->
    <UContainer class="py-6">
      <UTabs
        :items="items"
        class="w-full"
      >
        <template #documents>
          <DocumentsPanel />
        </template>

        <template #users>
          <UsersPanel />
        </template>

        <template #health>
          <HealthPanel />
        </template>

        <template #tree>
          <TreePanel />
        </template>
      </UTabs>
    </UContainer>
  </div>
</template>
