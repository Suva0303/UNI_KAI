<script setup lang="ts">
import axios from "axios";
import { onMounted, ref } from "vue";
import { toast } from "vue-sonner";
import { api } from "../../services/api";

type ArticleRow = {
  id: number;
  title: string;
  excerpt?: string | null;
  content?: string | null;
  category?: string | null;
  image_url?: string | null;
  created_at?: string | null;
};

const articles = ref<ArticleRow[]>([]);
const form = ref({ title: "", excerpt: "", content: "", category: "", image_url: "" });
const loading = ref(false);
const saving = ref(false);

function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data;
    if (typeof d === "string" && d.trim()) return d.trim();
    if (d && typeof d === "object" && "detail" in d) {
      const det = (d as { detail: unknown }).detail;
      if (typeof det === "string" && det.trim()) return det.trim();
      if (Array.isArray(det))
        return det.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join("; ");
    }
    return err.message || "Ошибка запроса";
  }
  return "Ошибка загрузки";
}

const load = async () => {
  loading.value = true;
  try {
    const { data } = await api.get<ArticleRow[]>("/api/admin/articles");
    articles.value = Array.isArray(data) ? data : [];
  } catch (e) {
    articles.value = [];
    toast.error(formatApiError(e));
  } finally {
    loading.value = false;
  }
};

const create = async () => {
  if (!form.value.title.trim()) {
    toast.error("Укажите заголовок статьи.");
    return;
  }
  saving.value = true;
  try {
    await api.post("/api/admin/articles", {
      title: form.value.title.trim(),
      excerpt: form.value.excerpt.trim() || null,
      content: form.value.content.trim() || null,
      category: form.value.category.trim() || null,
      image_url: form.value.image_url.trim() || null,
    });
    form.value = { title: "", excerpt: "", content: "", category: "", image_url: "" };
    toast.success("Статья добавлена");
    await load();
  } catch (e) {
    toast.error(formatApiError(e));
  } finally {
    saving.value = false;
  }
};

onMounted(load);
</script>

<template>
  <section class="space-y-6">
    <h1 class="text-3xl font-semibold">Управление статьями</h1>
    <p v-if="loading" class="text-sm text-charcoal/60">Загрузка из БД…</p>
    <div class="rounded-2xl bg-white p-4 shadow-soft">
      <h2 class="mb-3 text-lg font-semibold">Новая статья</h2>
      <div class="grid gap-3">
        <input v-model="form.title" class="rounded-2xl border border-pastel-lavender bg-ivory px-3 py-2" placeholder="Заголовок" />
        <input v-model="form.excerpt" class="rounded-2xl border border-pastel-blue bg-ivory px-3 py-2" placeholder="Краткое описание" />
        <input v-model="form.category" class="rounded-2xl border border-pastel-rose bg-ivory px-3 py-2" placeholder="Категория" />
        <input
          v-model="form.image_url"
          class="rounded-2xl border border-pastel-lavender bg-ivory px-3 py-2"
          placeholder="URL изображения (необязательно)"
          type="url"
        />
        <textarea v-model="form.content" class="min-h-32 rounded-2xl border border-pastel-mint bg-ivory px-3 py-2" placeholder="Содержимое"></textarea>
      </div>
      <button
        type="button"
        class="mt-3 rounded-2xl border border-pastel-mint bg-ivory px-3 py-2 hover:bg-pastel-mint/40 disabled:opacity-50"
        :disabled="saving"
        @click="create"
      >
        Добавить
      </button>
    </div>
    <div v-if="!loading && articles.length === 0" class="rounded-2xl border border-matte-lilac/80 bg-matte-dust/30 px-4 py-3 text-sm text-charcoal/70">
      Статей пока нет. После первого сохранения они появятся здесь и в разделе «Статьи» на сайте.
    </div>
    <div class="grid gap-4 md:grid-cols-2">
      <article v-for="article in articles" :key="article.id" class="rounded-2xl border border-pastel-peach bg-white p-4 shadow-soft">
        <div v-if="article.image_url" class="mb-3 overflow-hidden rounded-xl border border-pastel-lavender/50">
          <img :src="article.image_url" :alt="article.title" class="aspect-video w-full object-cover" loading="lazy" />
        </div>
        <h3 class="font-medium">{{ article.title }}</h3>
        <p class="mt-1 text-sm text-charcoal/70">{{ article.excerpt || "—" }}</p>
        <p v-if="article.category" class="mt-2 text-xs text-charcoal/50">{{ article.category }}</p>
      </article>
    </div>
  </section>
</template>
