<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../../services/api";

type ArticleListItem = {
  id: number;
  title: string;
  excerpt: string | null;
  category: string | null;
  image_url: string | null;
  created_at: string | null;
};

const articles = ref<ArticleListItem[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

const dateFmt = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "long",
  year: "numeric",
});

function formatDate(value: string | null): string {
  if (!value) return "Дата не указана";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Дата не указана";
  return dateFmt.format(date);
}

onMounted(async () => {
  loading.value = true;
  error.value = null;
  try {
    const { data } = await api.get<ArticleListItem[]>("/api/public/articles");
    articles.value = data ?? [];
  } catch {
    articles.value = [];
    error.value = "Не удалось загрузить статьи.";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section class="space-y-5">
    <header class="space-y-2">
      <h1 class="text-2xl font-semibold leading-tight text-charcoal md:text-3xl">Статьи</h1>
      <p class="text-sm text-charcoal/70">Подборка материалов по аналитике, образованию и трудоустройству выпускников.</p>
    </header>

    <p v-if="error" class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <p v-else-if="loading" class="text-sm text-charcoal/60">Загрузка статей…</p>
    <p v-else-if="articles.length === 0" class="rounded-xl border border-matte-lilac/80 bg-white px-4 py-3 text-sm text-charcoal/70">
      Пока нет опубликованных статей.
    </p>

    <div v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <router-link
        v-for="article in articles"
        :key="article.id"
        :to="`/articles/${article.id}`"
        class="group flex h-full flex-col overflow-hidden rounded-2xl border border-matte-lilac/90 bg-white shadow-sm transition hover:-translate-y-0.5 hover:border-pastel-lavender hover:shadow-md"
      >
        <div
          v-if="article.image_url"
          class="relative aspect-[1200/630] w-full overflow-hidden bg-[#ebe6f5]"
        >
          <img
            :src="article.image_url"
            :alt="article.title"
            class="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
            loading="lazy"
            decoding="async"
            referrerpolicy="no-referrer"
          />
        </div>
        <div class="flex flex-1 flex-col p-5">
          <div class="mb-3 flex items-center justify-between gap-3 text-xs text-charcoal/60">
            <span class="rounded-full bg-[#f3eefc] px-2.5 py-1 font-medium text-[#66508f]">
              {{ article.category || "Общее" }}
            </span>
            <span class="shrink-0">{{ formatDate(article.created_at) }}</span>
          </div>

          <h2 class="line-clamp-2 text-lg font-semibold leading-snug text-charcoal transition group-hover:text-[#4f3f73]">
            {{ article.title }}
          </h2>
          <p class="mt-2 line-clamp-4 text-sm leading-relaxed text-charcoal/70">
            {{ article.excerpt || "Откройте материал, чтобы прочитать полный текст статьи." }}
          </p>

          <div class="mt-auto pt-4 text-sm font-medium text-[#66508f]">Читать статью →</div>
        </div>
      </router-link>
    </div>
  </section>
</template>
