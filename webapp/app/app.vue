<script setup>
useHead({
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1' }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ],
  htmlAttrs: {
    lang: 'vi'
  }
})

const title = 'RAG Chatbot - Hỏi đáp tài liệu doanh nghiệp'
const description = 'Hệ thống hỏi đáp thông minh cho tài liệu doanh nghiệp Việt Nam'

useSeoMeta({
  title,
  description,
  ogTitle: title,
  ogDescription: description
})
</script>

<template>
  <UApp>
    <NuxtPage />
  </UApp>
</template>
