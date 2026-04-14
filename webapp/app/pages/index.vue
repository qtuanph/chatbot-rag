<script setup lang="ts">
import type { AuthFormField } from '@nuxt/ui'
import type { ApiError } from '../types/api'

const router = useRouter()
const toast = useToast()

const fields: AuthFormField[] = [
  {
    name: 'username',
    type: 'text',
    label: 'Tên đăng nhập',
    placeholder: 'Nhập tên đăng nhập',
    required: true
  },
  {
    name: 'password',
    type: 'password',
    label: 'Mật khẩu',
    placeholder: 'Nhập mật khẩu',
    required: true
  }
]

const isLoading = ref(false)

async function onSubmit(event: unknown) {
  try {
    isLoading.value = true

    // UAuthForm emits FormSubmitEvent with data property
    const e = event as { data: { username: string, password: string } }
    await apiClient.auth.login(e.data.username, e.data.password)

    toast.add({
      title: 'Đăng nhập thành công',
      description: 'Chào mừng bạn trở lại!',
      color: 'green',
      icon: 'i-lucide-check-circle'
    })

    // Redirect based on role
    const role = apiClient.auth.getUserRole()
    if (role === 'admin') {
      router.push('/admin')
    } else {
      router.push('/chat')
    }
  } catch (error) {
    toast.add({
      title: 'Đăng nhập thất bại',
      description: (error as ApiError).response?.data?.detail || 'Tên đăng nhập hoặc mật khẩu không đúng',
      color: 'red',
      icon: 'i-lucide-x-circle'
    })
  } finally {
    isLoading.value = false
  }
}

// Check if already authenticated
onMounted(() => {
  if (apiClient.auth.isAuthenticated()) {
    const role = apiClient.auth.getUserRole()
    if (role === 'admin') {
      router.push('/admin')
    } else {
      router.push('/chat')
    }
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md">
      <UCard class="shadow-lg">
        <template #header>
          <div class="text-center">
            <h1 class="text-2xl font-bold text-gray-900">
              RAG Chatbot
            </h1>
            <p class="mt-2 text-sm text-gray-600">
              Hệ thống hỏi đáp tài liệu doanh nghiệp
            </p>
          </div>
        </template>

        <UAuthForm
          :fields="fields"
          :submit="{ label: 'Đăng nhập', loading: isLoading }"
          @submit="onSubmit"
        />
      </UCard>

      <div class="mt-4 text-center text-sm text-gray-500">
        <p>Đăng nhập với:</p>
        <p class="mt-1 font-medium">
          admin / abc123 (Quản trị viên)
        </p>
        <p class="font-medium">
          member / abc123 (Thành viên)
        </p>
      </div>
    </div>
  </div>
</template>
