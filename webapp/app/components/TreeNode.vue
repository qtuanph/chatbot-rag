<script setup lang="ts">
interface TreeNode {
  id: string
  header: string
  content: string
  parent_id?: string
  children?: TreeNode[]
  level: number
  page_number: number
}

const props = defineProps<{
  node: TreeNode
}>()

const isOpen = ref(true)
</script>

<template>
  <div class="ml-4">
    <div
      class="flex cursor-pointer items-center gap-2 rounded p-2 hover:bg-gray-100"
      @click="isOpen = !isOpen"
    >
      <UIcon
        :name="isOpen ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
        class="h-4 w-4 text-gray-400"
      />
      <UIcon
        name="i-lucide-file"
        class="h-4 w-4 text-gray-600"
      />
      <span class="font-medium text-gray-900">{{ props.node.header || 'Untitled' }}</span>
    </div>
    <div
      v-if="isOpen"
      class="ml-6 mt-2 space-y-2"
    >
      <div
        v-if="props.node.content"
        class="rounded bg-gray-50 p-3 text-sm text-gray-700"
      >
        {{ props.node.content?.substring(0, 200) }}
        {{ props.node.content?.length > 200 ? '...' : '' }}
      </div>
      <TreeNode
        v-for="child in props.node.children || []"
        :key="child.id"
        :node="child"
      />
    </div>
  </div>
</template>
