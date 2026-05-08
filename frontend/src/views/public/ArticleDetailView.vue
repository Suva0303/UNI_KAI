<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "../../services/api";

const route = useRoute();

type ArticleDetail = {
  id: number;
  title: string;
  excerpt: string | null;
  content: string | null;
  category: string | null;
  image_url: string | null;
  created_at: string | null;
};

const article = ref<ArticleDetail | null>(null);
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
    const { data } = await api.get<ArticleDetail>(`/api/public/articles/${route.params.id}`);
    article.value = data;
  } catch {
    article.value = null;
    error.value = "Статья не найдена или временно недоступна.";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section class="space-y-4">
    <p v-if="loading" class="text-sm text-charcoal/60">Загрузка статьи…</p>
    <p v-else-if="error" class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{{ error }}</p>

    <article
      v-else-if="article"
      class="mx-auto w-full max-w-4xl rounded-2xl border border-matte-lilac/80 bg-white px-5 py-6 shadow-sm md:px-10 md:py-9"
    >
      <header class="border-b border-matte-lilac/70 pb-5 md:pb-6">
        <div class="mb-3 flex flex-wrap items-center gap-2 text-xs">
          <span class="rounded-full bg-[#f3eefc] px-2.5 py-1 font-medium text-[#66508f]">
            {{ article.category || "Общее" }}
          </span>
          <span class="text-charcoal/60">{{ formatDate(article.created_at) }}</span>
        </div>
        <h1 class="text-2xl font-semibold leading-tight text-charcoal md:text-4xl md:leading-[1.2]">
          {{ article.title || "Статья" }}
        </h1>
        <p v-if="article.excerpt" class="mt-4 text-base leading-relaxed text-charcoal/75 md:text-lg">
          {{ article.excerpt }}
        </p>
      </header>

      <figure
        v-if="article.image_url"
        class="mt-6 overflow-hidden rounded-2xl border border-matte-lilac/60 bg-[#f3effa] md:mt-8"
      >
        <img
          :src="article.image_url"
          :alt="article.title"
          class="aspect-[1200/630] w-full object-cover"
          loading="eager"
          decoding="async"
          referrerpolicy="no-referrer"
        />
      </figure>

      <div class="prose prose-zinc mt-6 max-w-none whitespace-pre-line text-[16px] leading-8 text-charcoal md:mt-8">
        {{ article.content || "Текст статьи отсутствует." }}
      </div>
    </article>
  </section>
</template>
