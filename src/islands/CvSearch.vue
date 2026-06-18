<script setup lang="ts">
import { ref, computed } from 'vue';

interface Cv {
  id: string;
  name: string;
  avatar_url?: string;
  bio?: string;
}

const props = defineProps<{
  cvs: Cv[];
}>();

const query = ref('');

const results = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return [];
  return props.cvs
    .filter((cv) => cv.name.toLowerCase().includes(q))
    .slice(0, 12);
});
</script>

<template>
  <div class="card">
    <div class="relative">
      <input
        v-model="query"
        type="text"
        placeholder="输入 CV 名字进行模糊搜索..."
        class="w-full px-4 py-3 pl-12 rounded-xl bg-bg-darker border border-border text-text placeholder:text-text-muted focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/20 transition-all"
      />
      <svg
        class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
    </div>

    <!-- 搜索结果 -->
    <div v-if="results.length" class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <a
        v-for="cv in results"
        :key="cv.id"
        :href="`/cvs/${cv.id}/`"
        class="flex items-center gap-3 p-3 rounded-xl bg-bg-darker border border-border hover:border-brand-500/40 hover:-translate-y-0.5 transition-all"
      >
        <img
          v-if="cv.avatar_url"
          :src="cv.avatar_url"
          :alt="cv.name"
          class="w-10 h-10 rounded-xl object-cover bg-gradient-to-br from-brand-400/20 to-accent-400/20"
          loading="lazy"
        />
        <div
          v-else
          class="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-400 via-accent-400 to-cyanx-500 flex items-center justify-center text-lg text-white font-bold shadow-lg shadow-brand-500/20"
        >
          {{ cv.name.slice(0, 1) }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="font-medium text-text-soft truncate">{{ cv.name }}</div>
          <div v-if="cv.bio" class="text-xs text-text-muted truncate">{{ cv.bio }}</div>
        </div>
      </a>
    </div>

    <p v-else-if="query.trim()" class="mt-4 text-sm text-text-muted">
      未找到匹配的 CV，请尝试其他关键词。
    </p>
  </div>
</template>
