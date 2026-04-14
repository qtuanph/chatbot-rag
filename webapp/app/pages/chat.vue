<script setup lang="ts">
import type { Citation, ApiError } from '../types/api'

const router = useRouter()
const toast = useToast()

const isLoading = ref(false)
const query = ref('')

interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  suggestions?: string[]
}
const messages = ref<Message[]>([])
const username = ref('')

// Welcome message
const welcomeMessage = {
  role: 'assistant',
  content: 'Xin chào! Tôi là trợ lý AI hỏi đáp tài liệu. Bạn có thể hỏi tôi về bất kỳ tài liệu nào đã được tải lên hệ thống.',
  suggestions: [
    'Tài liệu nào có trong hệ thống?',
    'Tìm kiếm thông tin về...',
    'Có những tài liệu nào mới nhất?'
  ]
}

// Load messages from session storage or show welcome
onMounted(() => {
  if (!apiClient.auth.isAuthenticated()) {
    router.push('/')
    return
  }

  // Get username from localStorage
  username.value = localStorage.getItem('username') || 'Người dùng'

  const stored = sessionStorage.getItem('chatMessages')
  if (stored) {
    messages.value = JSON.parse(stored)
  } else {
    messages.value = [welcomeMessage]
  }
})

// Save messages to session storage
watch(messages, (newMessages) => {
  if (import.meta.client) {
    sessionStorage.setItem('chatMessages', JSON.stringify(newMessages))
  }
}, { deep: true })

async function sendMessage() {
  if (!query.value.trim() || isLoading.value) return

  const userMessage = query.value
  query.value = ''

  // Add user message
  messages.value.push({
    role: 'user',
    content: userMessage
  })

  try {
    isLoading.value = true

    // Call API
    const response = await apiClient.chat.sendMessage(userMessage)

    messages.value.push({
      role: 'assistant',
      content: response.answer,
      citations: response.citations || []
    })

    // Scroll to bottom
    nextTick(() => {
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
    })
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || 'Không thể gửi tin nhắn',
      color: 'red',
      icon: 'i-lucide-x-circle'
    })

    // Remove user message on error
    messages.value.pop()
  } finally {
    isLoading.value = false
  }
}

function handleSuggestion(suggestion: string) {
  query.value = suggestion
  sendMessage()
}

async function logout() {
  try {
    await apiClient.auth.logout()
    sessionStorage.removeItem('chatMessages')
    router.push('/')
  } catch {
    // Force logout even on error
    sessionStorage.removeItem('chatMessages')
    router.push('/')
  }
}
</script>

<template>
  <div class="flex h-screen flex-col bg-gray-50">
    <!-- Header -->
    <UContainer class="border-b border-gray-200 bg-white py-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-xl font-bold text-gray-900">
            Hỏi đáp tài liệu
          </h1>
          <p class="text-sm text-gray-500">
            Đăng nhập sebagai: {{ username }}
          </p>
        </div>
        <UButton
          icon="i-lucide-log-out"
          color="neutral"
          variant="ghost"
          @click="logout"
        >
          Đăng xuất
        </UButton>
      </div>
    </UContainer>

    <!-- Messages -->
    <div class="flex-1 overflow-y-auto p-4">
      <UContainer>
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="mb-6"
        >
          <!-- User message -->
          <div
            v-if="message.role === 'user'"
            class="flex justify-end"
          >
            <div class="max-w-[80%] rounded-lg bg-blue-500 p-4 text-white">
              <p class="whitespace-pre-wrap">
                {{ message.content }}
              </p>
            </div>
          </div>

          <!-- Assistant message -->
          <div
            v-else
            class="flex justify-start"
          >
            <div class="max-w-[80%] rounded-lg bg-white p-4 shadow-sm">
              <!-- Welcome message with suggestions -->
              <div v-if="message.suggestions">
                <p class="whitespace-pre-wrap text-gray-900">
                  {{ message.content }}
                </p>
                <div class="mt-4 flex flex-wrap gap-2">
                  <UButton
                    v-for="(suggestion, idx) in message.suggestions"
                    :key="idx"
                    size="xs"
                    color="neutral"
                    variant="soft"
                    @click="handleSuggestion(suggestion)"
                  >
                    {{ suggestion }}
                  </UButton>
                </div>
              </div>

              <!-- Regular message -->
              <div v-else>
                <p class="whitespace-pre-wrap text-gray-900">
                  {{ message.content }}
                </p>

                <!-- Citations -->
                <div
                  v-if="message.citations && message.citations.length > 0"
                  class="mt-4 border-t border-gray-200 pt-4"
                >
                  <p class="mb-2 text-sm font-semibold text-gray-700">
                    Nguồn:
                  </p>
                  <div class="space-y-2">
                    <div
                      v-for="(citation, idx) in message.citations"
                      :key="idx"
                      class="rounded bg-gray-50 p-3 text-sm"
                    >
                      <p class="font-medium text-gray-900">
                        {{ citation.file_name || 'Tài liệu' }}
                      </p>
                      <p class="text-gray-600">
                        {{ citation.node_header || 'Không có tiêu đề' }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Loading indicator -->
        <div
          v-if="isLoading"
          class="mb-6 flex justify-start"
        >
          <div class="rounded-lg bg-white p-4 shadow-sm">
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-loader-2"
                class="h-4 w-4 animate-spin text-blue-500"
              />
              <p class="text-sm text-gray-600">
                Đang suy nghĩ...
              </p>
            </div>
          </div>
        </div>
      </UContainer>
    </div>

    <!-- Input -->
    <div class="border-t border-gray-200 bg-white p-4">
      <UContainer>
        <form @submit.prevent="sendMessage">
          <div class="flex gap-2">
            <UTextarea
              v-model="query"
              placeholder="Nhập câu hỏi của bạn..."
              :disabled="isLoading"
              autoresize
              :rows="1"
              class="flex-1"
            />
            <UButton
              type="submit"
              icon="i-lucide-send"
              :loading="isLoading"
              :disabled="!query.trim()"
              color="primary"
            >
              Gửi
            </UButton>
          </div>
        </form>
      </UContainer>
    </div>
  </div>
</template>
