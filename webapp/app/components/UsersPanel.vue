<script setup lang="ts">
import type { CreateUserRequest, ApiError } from '../types/api'

interface User {
  id: string
  username: string
  role: string
  created_at: string
}

const toast = useToast()
const users = ref<User[]>([])
const isLoading = ref(false)

const newUser = ref<CreateUserRequest>({
  username: '',
  password: '',
  role: 'member'
})

async function loadUsers() {
  try {
    isLoading.value = true
    users.value = await apiClient.users.list()
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || 'Không thể tải danh sách người dùng',
      color: 'red'
    })
  } finally {
    isLoading.value = false
  }
}

async function createUser() {
  if (!newUser.value.username || !newUser.value.password) {
    toast.add({
      title: 'Lỗi',
      description: 'Vui lòng nhập đầy đủ thông tin',
      color: 'red'
    })
    return
  }

  try {
    isLoading.value = true
    await apiClient.users.create(newUser.value)

    toast.add({
      title: 'Thành công',
      description: 'Đã tạo người dùng',
      color: 'green'
    })

    newUser.value = { username: '', password: '', role: 'member' }
    await loadUsers()
  } catch (error) {
    toast.add({
      title: 'Lỗi',
      description: (error as ApiError).response?.data?.detail || 'Không thể tạo người dùng',
      color: 'red'
    })
  } finally {
    isLoading.value = false
  }
}

async function deleteUser(username: string) {
  if (!confirm(`Bạn có chắc chắn muốn xóa người dùng "${username}"?`)) return

  try {
    isLoading.value = true
    await apiClient.users.delete(username)

    toast.add({
      title: 'Thành công',
      description: 'Đã xóa người dùng',
      color: 'green'
    })

    await loadUsers()
  } catch (error) {
    const apiError = error as ApiError
    toast.add({
      title: 'Lỗi',
      description: apiError.response?.data?.detail || 'Không thể xóa người dùng',
      color: 'red'
    })
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<template>
  <div class="space-y-4">
    <!-- Create user -->
    <UCard>
      <h3 class="mb-4 text-lg font-semibold">
        Tạo người dùng mới
      </h3>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-4">
        <UInput
          v-model="newUser.username"
          placeholder="Tên đăng nhập"
          :disabled="isLoading"
        />
        <UInput
          v-model="newUser.password"
          type="password"
          placeholder="Mật khẩu"
          :disabled="isLoading"
        />
        <USelect
          v-model="newUser.role"
          :items="[
            { label: 'Thành viên', value: 'member' },
            { label: 'Quản trị viên', value: 'admin' }
          ]"
          :disabled="isLoading"
        />
        <UButton
          icon="i-lucide-plus"
          :loading="isLoading"
          @click="createUser"
        >
          Tạo
        </UButton>
      </div>
    </UCard>

    <!-- Users list -->
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold">
            Danh sách người dùng
          </h3>
          <UButton
            icon="i-lucide-refresh-cw"
            size="sm"
            color="neutral"
            variant="ghost"
            :loading="isLoading"
            @click="loadUsers"
          />
        </div>
      </template>

      <div
        v-if="isLoading && users.length === 0"
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
        v-else-if="users.length === 0"
        class="py-8 text-center"
      >
        <p class="text-gray-500">
          Chưa có người dùng nào
        </p>
      </div>

      <div
        v-else
        class="space-y-2"
      >
        <div
          v-for="user in users"
          :key="user.username"
          class="flex items-center justify-between rounded-lg border border-gray-200 p-4"
        >
          <div class="flex-1">
            <p class="font-medium text-gray-900">
              {{ user.username }}
            </p>
            <div class="mt-1 flex items-center gap-4 text-sm text-gray-500">
              <span>
                <UBadge
                  :color="user.role === 'admin' ? 'blue' : 'gray'"
                  variant="soft"
                  size="xs"
                >
                  {{ user.role === 'admin' ? 'Quản trị viên' : 'Thành viên' }}
                </UBadge>
              </span>
              <span v-if="user.created_at">
                {{ new Date(user.created_at).toLocaleDateString('vi-VN') }}
              </span>
            </div>
          </div>
          <UButton
            icon="i-lucide-trash-2"
            color="red"
            variant="ghost"
            size="sm"
            :disabled="user.username === 'admin'"
            @click="deleteUser(user.username)"
          />
        </div>
      </div>
    </UCard>
  </div>
</template>
