<script setup lang="ts">
import axios from "axios";
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import EmploymentFlask from "../../components/EmploymentFlask.vue";
import { api } from "../../services/api";
import type { RegionOption, UniversitiesMeta, UniversityListRow } from "../../types/dashboard";

const route = useRoute();
const router = useRouter();

const meta = ref<UniversitiesMeta | null>(null);
const regions = ref<RegionOption[]>([]);
const items = ref<UniversityListRow[]>([]);
const totalFiltered = ref(0);
const loading = ref(false);
const error = ref<string | null>(null);

const searchText = ref("");
const regionId = ref<number | null>(null);
const sortBy = ref<"rating" | "salary" | "employment">("rating");

let searchTimer: ReturnType<typeof setTimeout> | null = null;

function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data;
    if (typeof d === "string" && d.trim()) return d.trim();
    if (d && typeof d === "object" && "detail" in d) {
      const det = (d as { detail: unknown }).detail;
      if (typeof det === "string" && det.trim()) return det.trim();
    }
    const msg = err.message || "Ошибка запроса";
    if (err.response?.status === 404) {
      return `${msg} Проверьте адрес API (VITE_API_BASE_URL без суффикса /api) и что запущен бэкенд.`;
    }
    return msg;
  }
  return "Ошибка загрузки";
}

async function loadMeta() {
  try {
    const { data } = await api.get<UniversitiesMeta>("/api/public/universities-meta");
    meta.value = data;
  } catch {
    meta.value = { universities_total: 0, data_year: new Date().getFullYear() };
  }
}

async function loadRegions() {
  try {
    const { data } = await api.get<RegionOption[]>("/api/public/regions");
    regions.value = data ?? [];
  } catch {
    regions.value = [];
  }
}

function mapUniversityRow(r: UniversityListRow): UniversityListRow {
  const compositeRaw = r.composite_score;
  const composite = compositeRaw == null ? undefined : Number(compositeRaw);
  return {
    ...r,
    university_id: Number(r.university_id),
    avg_salary: Number(r.avg_salary ?? 0),
    employment_rate: Number(r.employment_rate ?? 0),
    employed_count: Number(r.employed_count ?? 0),
    specialty_rate: Number(r.specialty_rate ?? 0),
    composite_score: composite != null && !Number.isNaN(composite) ? composite : undefined,
    rating: r.rating == null ? null : Number(r.rating),
    region_name: String(r.region_name ?? ""),
  };
}

async function loadUniversities() {
  loading.value = true;
  error.value = null;
  const pageSize = 2000;
  const acc: UniversityListRow[] = [];
  try {
    let page = 1;
    let total = 0;
    for (;;) {
      const { data } = await api.get<{ items: UniversityListRow[]; total: number }>("/api/public/universities", {
        params: {
          page,
          page_size: pageSize,
          search: searchText.value.trim() || undefined,
          region_id: regionId.value ?? undefined,
          sort: sortBy.value,
        },
      });
      total = Number(data.total ?? 0);
      const batch = (data.items ?? []).map(mapUniversityRow);
      acc.push(...batch);
      if (batch.length < pageSize || acc.length >= total || page > 40) break;
      page += 1;
    }
    items.value = acc;
    totalFiltered.value = total;
  } catch (e) {
    error.value = formatApiError(e);
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function scheduleSearch() {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchTimer = null;
    void loadUniversities();
    void router.replace({
      query: { ...route.query, search: searchText.value.trim() || undefined },
    });
  }, 320);
}

onMounted(async () => {
  searchText.value = String(route.query.search || "");
  await Promise.all([loadMeta(), loadRegions(), loadUniversities()]);
});

watch([regionId, sortBy], () => {
  void loadUniversities();
});

const moneyFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
</script>

<template>
  <section class="space-y-5">
    <header class="space-y-2">
      <h1 class="text-2xl font-semibold leading-tight text-charcoal md:text-3xl">Высшие учебные заведения России</h1>
      <p v-if="meta" class="text-sm text-charcoal/70">
        Вузов в каталоге: <span class="font-medium text-charcoal">{{ meta.universities_total }}</span>
        <span class="mx-2 text-charcoal/35">·</span>
        Данные за: <span class="font-medium text-charcoal">{{ meta.data_year }}</span>
        г.
        <span v-if="totalFiltered !== meta.universities_total" class="block pt-1 text-charcoal/60">
          По фильтрам показано: {{ totalFiltered }}
        </span>
      </p>
    </header>

    <div class="flex flex-wrap items-end gap-3 md:flex-nowrap">
      <label class="flex min-w-[180px] flex-1 flex-col gap-1">
        <span class="text-xs font-medium text-charcoal/65">Поиск по вузу или региону</span>
        <input
          v-model="searchText"
          type="search"
          placeholder="Название, город, регион…"
          class="rounded-xl border border-matte-lilac/90 bg-white px-3 py-2 text-sm text-charcoal shadow-sm"
          @input="scheduleSearch"
        />
      </label>
      <label class="flex min-w-[160px] flex-col gap-1">
        <span class="text-xs font-medium text-charcoal/65">Регион</span>
        <select
          v-model="regionId"
          class="rounded-xl border border-matte-lilac/90 bg-white px-3 py-2 text-sm text-charcoal shadow-sm"
        >
          <option :value="null">Все регионы</option>
          <option v-for="r in regions" :key="r.region_id" :value="r.region_id">{{ r.region_name }}</option>
        </select>
      </label>
      <label class="flex min-w-[220px] flex-col gap-1">
        <span class="text-xs font-medium text-charcoal/65">Сортировка</span>
        <select v-model="sortBy" class="rounded-xl border border-matte-lilac/90 bg-white px-3 py-2 text-sm text-charcoal shadow-sm">
          <option value="rating">По рейтингу</option>
          <option value="salary">По зарплате</option>
          <option value="employment">По трудоустройству</option>
        </select>
      </label>
    </div>

    <p v-if="error" class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <p v-if="loading" class="text-sm text-charcoal/60">Загрузка списка…</p>

    <div
      class="hidden rounded-xl border border-matte-lilac/80 bg-white/80 px-4 py-2.5 text-xs font-semibold text-charcoal/60 shadow-sm md:grid md:grid-cols-[3.5rem_minmax(0,1fr)_7.5rem_7rem_minmax(10.5rem,12rem)] md:items-center md:gap-3"
    >
      <span class="text-center">№</span>
      <span>Название</span>
      <span>Город</span>
      <span class="text-right">Ср. зарплата</span>
      <span class="text-center">Трудоустр.</span>
    </div>

    <div class="space-y-3">
      <router-link
        v-for="(u, idx) in items"
        :key="u.university_id"
        :to="`/universities/${u.university_id}`"
        class="grid cursor-pointer grid-cols-1 gap-3 rounded-2xl border border-matte-lilac/90 bg-white p-4 shadow-sm transition hover:border-pastel-lavender hover:shadow-md md:min-h-[7.25rem] md:grid-cols-[3.5rem_minmax(0,1fr)_7.5rem_7rem_minmax(10.5rem,12rem)] md:items-center md:gap-4"
      >
        <div class="flex items-start justify-between gap-3 md:contents">
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#f1ebfa] text-sm font-semibold tabular-nums text-[#6b5b8c] md:h-auto md:w-auto md:rounded-none md:bg-transparent md:text-xl">
            {{ idx + 1 }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="font-semibold leading-snug text-charcoal md:font-medium">
              {{ u.university_name }}
            </div>
            <div class="mt-1 text-sm text-charcoal/70 md:hidden">
              {{ u.city_name || "Город не указан" }}
            </div>
          </div>
          <div class="hidden min-h-[2.5rem] items-center text-sm text-charcoal/75 md:flex">{{ u.city_name || "—" }}</div>
        </div>

        <div class="grid grid-cols-2 gap-2 rounded-xl bg-[#faf8fe] p-2.5 md:contents md:rounded-none md:bg-transparent md:p-0">
          <div class="rounded-lg bg-white px-2.5 py-2 md:min-h-[2.5rem] md:items-center md:justify-end md:bg-transparent md:px-0 md:py-0">
            <div class="text-[11px] font-medium uppercase tracking-wide text-charcoal/55 md:hidden">Ср. зарплата</div>
            <div class="text-sm font-semibold tabular-nums text-charcoal md:text-sm md:font-medium">
              {{ moneyFmt.format(u.avg_salary) }}&nbsp;₽
            </div>
          </div>
          <div class="rounded-lg bg-white px-2.5 py-2 md:flex md:w-full md:min-h-0 md:items-center md:justify-center md:bg-transparent md:px-0 md:py-0">
            <div class="mb-1 text-[11px] font-medium uppercase tracking-wide text-charcoal/55 md:hidden">Трудоустр.</div>
            <div class="flex w-full min-h-0 items-center justify-stretch">
              <EmploymentFlask :percent="u.employment_rate" />
            </div>
          </div>
        </div>
      </router-link>
    </div>
  </section>
</template>
