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

  // Add placeholder for assistant message
  const assistantMessageIndex = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: '',
    citations: []
  })

  try {
    isLoading.value = true

    // Use streaming API
    const config = useRuntimeConfig()
    const token = localStorage.getItem('token')

    const response = await fetch(`${config.public.apiBase}/api/v1/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ query: userMessage })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('No response body')
    }

    let buffer = ''
    let finalCitations: Citation[] = []

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Process SSE data: lines
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || '' // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6))

            if (data.error) {
              throw new Error(data.error)
            }

            if (data.chunk) {
              // Append chunk to current message
              messages.value[assistantMessageIndex].content += data.chunk
            }

            if (data.done) {
              // Stream complete
              if (data.citations) {
                finalCitations = data.citations
                messages.value[assistantMessageIndex].citations = finalCitations
              }
              isLoading.value = false
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e)
          }
        }
      }
    }

    // Scroll to bottom after each chunk
    nextTick(() => {
      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
    })
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || apiError.message || 'Không thể gửi tin nhắn',
      color: 'red',
      icon: 'i-lucide-x-circle'
    })

    // Remove both user and assistant message on error
    messages.value.splice(assistantMessageIndex - 1, 2)
  } finally {
    isLoading.value = false
  }
}

function handleSuggestion(suggestion: string) {
  query.value = suggestion
  sendMessage()
}

// Get unique citations (deduplicate by title)
function uniqueCitations(citations: Citation[]) {
  const seen = new Set<string>()
  return citations.filter(citation => {
    const title = citation.title || 'Tài liệu'
    if (seen.has(title)) {
      return false
    }
    seen.add(title)
    return true
  })
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
            <div class="max-w-[80%] rounded-2xl rounded-br-md bg-gradient-to-br from-blue-500 to-blue-600 p-4 shadow-md text-white">
              <p class="whitespace-pre-wrap leading-relaxed">
                {{ message.content }}
              </p>
            </div>
          </div>

          <!-- Assistant message -->
          <div
            v-else
            class="flex justify-start"
          >
            <div class="max-w-[80%] rounded-2xl rounded-bl-md bg-white p-5 shadow-md border border-gray-100">
              <!-- Welcome message with suggestions -->
              <div v-if="message.suggestions">
                <p class="whitespace-pre-wrap text-gray-900 leading-relaxed">
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
                <p class="whitespace-pre-wrap text-gray-900 leading-relaxed">
                  {{ message.content }}
                </p>

                <!-- Citations - List all unique sources used -->
                <div
                  v-if="message.citations && message.citations.length > 0"
                  class="mt-4 border-t border-gray-100 pt-3"
                >
                  <p class="mb-2 text-xs font-medium text-gray-600">
                    📚 Tài liệu tham khảo:
                  </p>
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="(citation, idx) in uniqueCitations(message.citations)"
                      :key="idx"
                      class="inline-flex items-center rounded-full bg-gradient-to-r from-blue-50 to-indigo-50 px-3 py-1.5 text-xs font-medium text-blue-700 border border-blue-100"
                    >
                      {{ citation.title || 'Tài liệu' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Loading indicator - Beautiful typing animation -->
        <div
          v-if="isLoading"
          class="mb-6 flex justify-start"
        >
          <div class="rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 p-5 shadow-lg">
            <div class="flex items-center gap-3">
              <div class="flex gap-1">
                <div class="h-2 w-2 animate-bounce rounded-full bg-blue-500 [animation-delay:-0.3s]" />
                <div class="h-2 w-2 animate-bounce rounded-full bg-blue-500 [animation-delay:-0.15s]" />
                <div class="h-2 w-2 animate-bounce rounded-full bg-blue-500" />
              </div>
              <p class="text-sm font-medium text-gray-700">
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
