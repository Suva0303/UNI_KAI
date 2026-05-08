<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { AlertTriangle, ExternalLink, Pencil, Plus, Trash2, X } from "lucide-vue-next";
import { toast } from "vue-sonner";
import EmploymentFlask from "../../components/EmploymentFlask.vue";
import AdminUniversityFormModal from "../../components/admin/AdminUniversityFormModal.vue";
import { api } from "../../services/api";
import type { AdminCityOption, AdminUniversityDetail, RegionOption, UniversitiesMeta, UniversityListRow } from "../../types/dashboard";

const route = useRoute();
const router = useRouter();

const meta = ref<UniversitiesMeta | null>(null);
const regions = ref<RegionOption[]>([]);
const items = ref<UniversityListRow[]>([]);
const totalFiltered = ref(0);
const dimCatalogTotal = ref<number | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const cities = ref<AdminCityOption[]>([]);

const searchText = ref("");
const regionId = ref<number | null>(null);
const sortBy = ref<"rating" | "salary" | "employment">("rating");

let searchTimer: ReturnType<typeof setTimeout> | null = null;

const modalOpen = ref(false);
const modalMode = ref<"create" | "edit">("create");
const modalInitial = ref<AdminUniversityDetail | null>(null);
const loadingEdit = ref(false);

const deleteTarget = ref<UniversityListRow | null>(null);
const deleteSubmitting = ref(false);

function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data;
    if (d && typeof d === "object" && "detail" in d) {
      const det = (d as { detail: unknown }).detail;
      if (typeof det === "string" && det.trim()) return det.trim();
    }
    const msg = err.message || "Ошибка запроса";
    if (err.response?.status === 404) {
      return `${msg} Проверьте, что API доступен и VITE_API_BASE_URL без суффикса /api.`;
    }
    return msg;
  }
  return "Ошибка загрузки";
}

function apiErrorDetail(err: unknown): string | undefined {
  if (!axios.isAxiosError(err)) return undefined;
  const d = err.response?.data as { detail?: unknown } | undefined;
  const det = d?.detail;
  return typeof det === "string" ? det : undefined;
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

async function loadCities() {
  try {
    const { data } = await api.get<AdminCityOption[]>("/api/admin/cities");
    cities.value = (data ?? []).map((c) => ({
      city_id: Number(c.city_id),
      city_name: String(c.city_name ?? ""),
      region_name: String(c.region_name ?? ""),
    }));
  } catch {
    cities.value = [];
  }
}

function mapUniversityRow(r: UniversityListRow): UniversityListRow {
  const composite =
    r.composite_score != null && r.composite_score !== "" ? Number(r.composite_score) : undefined;
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

const selectedRegionName = computed(() => {
  if (regionId.value == null) return undefined;
  const name = regions.value.find((x) => x.region_id === regionId.value)?.region_name?.trim();
  return name || undefined;
});

type UniversitiesPagePayload = {
  items: UniversityListRow[];
  total: number;
  dim_catalog_total?: number;
};

async function fetchUniversitiesPage(
  page: number,
  pageSize: number,
): Promise<UniversitiesPagePayload> {
  const search = searchText.value.trim() || undefined;
  const dimParams = {
    page,
    page_size: pageSize,
    search,
    region_name: selectedRegionName.value,
    sort: sortBy.value,
  };
  const browserParams = {
    page,
    page_size: pageSize,
    search,
    region_id: regionId.value ?? undefined,
    sort: sortBy.value,
  };
  const paths = ["/api/admin/dim-universities", "/api/admin/universities-browser"] as const;
  let lastErr: unknown;
  for (const path of paths) {
    try {
      const { data } = await api.get<UniversitiesPagePayload>(path, {
        params: path.endsWith("dim-universities") ? dimParams : browserParams,
      });
      return data;
    } catch (e) {
      lastErr = e;
      if (axios.isAxiosError(e) && e.response?.status === 404) continue;
      throw e;
    }
  }
  throw lastErr;
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
      const data = await fetchUniversitiesPage(page, pageSize);
      if (data.dim_catalog_total != null) dimCatalogTotal.value = Number(data.dim_catalog_total);
      total = Number(data.total ?? 0);
      const batch = (data.items ?? []).map(mapUniversityRow);
      acc.push(...batch);
      if (batch.length < pageSize || acc.length >= total || page > 40) break;
      page += 1;
    }
    items.value = acc;
    totalFiltered.value = total;
  } catch (e) {
    error.value = apiErrorDetail(e) ?? formatApiError(e);
    items.value = [];
    totalFiltered.value = 0;
    dimCatalogTotal.value = null;
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

function openCreate() {
  modalMode.value = "create";
  modalInitial.value = null;
  modalOpen.value = true;
}

async function openEdit(id: number) {
  loadingEdit.value = true;
  try {
    const { data } = await api.get<AdminUniversityDetail>(`/api/admin/universities/${id}`);
    modalMode.value = "edit";
    modalInitial.value = {
      university_id: Number(data.university_id),
      university_code: String(data.university_code ?? ""),
      university_name: String(data.university_name ?? ""),
      city_id: data.city_id != null ? Number(data.city_id) : null,
      city_name: data.city_name ?? null,
      foundation_year: data.foundation_year != null ? Number(data.foundation_year) : null,
      rating: data.rating != null ? Number(data.rating) : null,
      website: data.website ?? null,
      description: data.description ?? null,
      logo_url: data.logo_url ?? null,
    };
    modalOpen.value = true;
  } catch (e) {
    toast.error(apiErrorDetail(e) ?? "Не удалось загрузить вуз для редактирования.");
  } finally {
    loadingEdit.value = false;
  }
}

function openDeleteConfirm(u: UniversityListRow) {
  deleteTarget.value = u;
}

function cancelDelete() {
  deleteTarget.value = null;
}

async function confirmDelete() {
  const u = deleteTarget.value;
  if (!u) return;
  deleteSubmitting.value = true;
  try {
    await api.delete(`/api/admin/universities/${u.university_id}`);
    toast.success("Вуз удалён из базы данных.");
    deleteTarget.value = null;
    await loadUniversities();
    await loadMeta();
  } catch (e) {
    const msg = apiErrorDetail(e);
    toast.error(msg ?? "Не удалось удалить вуз.");
  } finally {
    deleteSubmitting.value = false;
  }
}

function onModalSaved() {
  toast.success(modalMode.value === "create" ? "Вуз создан" : "Изменения сохранены");
  void loadUniversities();
  void loadMeta();
}

onMounted(async () => {
  searchText.value = String(route.query.search || "");
  await Promise.all([loadMeta(), loadRegions(), loadCities()]);
  await loadUniversities();
});

watch([regionId, sortBy], () => {
  void loadUniversities();
});

const moneyFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
</script>

<template>
  <section class="space-y-5">
    <header class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div class="space-y-2">
        <h1 class="text-2xl font-semibold leading-tight text-charcoal md:text-3xl">Управление вузами</h1>
        <p v-if="meta" class="text-sm text-charcoal/70">
          Вузов в каталоге: <span class="font-medium text-charcoal">{{ meta.universities_total }}</span>
          <span class="mx-2 text-charcoal/35">·</span>
          Данные за: <span class="font-medium text-charcoal">{{ meta.data_year }}</span>
          г.
          <span
            v-if="!error && totalFiltered !== meta.universities_total"
            class="block pt-1 text-charcoal/60"
          >
            По фильтрам показано: {{ totalFiltered }}
          </span>
        </p>
        <p v-if="dimCatalogTotal != null" class="text-xs text-charcoal/55">
          В справочнике БД (dwh.dim_university):
          <span class="font-medium text-charcoal">{{ dimCatalogTotal }}</span>
          вузов. В таблице ниже — та же выборка с фильтрами; метрики ЗП/трудоустройства из mart, без витрины —
          нули.
        </p>
      </div>
      <button
        type="button"
        class="inline-flex shrink-0 items-center justify-center gap-2 rounded-2xl border border-matte-sage/90 bg-matte-sage/40 px-5 py-3 text-sm font-semibold text-charcoal shadow-sm transition hover:bg-matte-sage/60"
        @click="openCreate"
      >
        <Plus class="h-4 w-4" stroke-width="2" aria-hidden="true" />
        Добавить вуз
      </button>
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
      class="hidden rounded-xl border border-matte-lilac/80 bg-white/80 px-4 py-2.5 text-xs font-semibold text-charcoal/60 shadow-sm md:grid md:grid-cols-[3.5rem_minmax(0,1fr)_7.5rem_7rem_minmax(10.5rem,12rem)_10.5rem] md:items-center md:gap-3"
    >
      <span class="text-center">№</span>
      <span>Название</span>
      <span>Город</span>
      <span class="text-right">Ср. зарплата</span>
      <span class="text-center">Трудоустр.</span>
      <span class="text-center">Действия</span>
    </div>

    <div class="space-y-3">
      <div
        v-for="(u, idx) in items"
        :key="u.university_id"
        class="grid min-h-[8.5rem] grid-cols-1 gap-3 rounded-2xl border border-matte-lilac/90 bg-white p-4 shadow-sm md:min-h-[7.25rem] md:grid-cols-[3.5rem_minmax(0,1fr)_7.5rem_7rem_minmax(10.5rem,12rem)_10.5rem] md:items-center md:gap-4"
      >
        <div class="flex items-center justify-center text-lg font-semibold tabular-nums text-[#6b5b8c] md:text-xl">
          {{ idx + 1 }}
        </div>
        <div class="flex min-h-[2.75rem] min-w-0 items-center">
          <div class="font-medium leading-snug text-charcoal">{{ u.university_name }}</div>
        </div>
        <div class="flex min-h-[2.5rem] items-center text-sm text-charcoal/75">{{ u.city_name || "—" }}</div>
        <div class="flex min-h-[2.5rem] items-center justify-end text-sm font-medium tabular-nums text-charcoal">
          {{ moneyFmt.format(u.avg_salary) }}&nbsp;₽
        </div>
        <div class="flex w-full min-h-0 items-center justify-stretch md:justify-center">
          <EmploymentFlask :percent="u.employment_rate" />
        </div>
        <div class="flex flex-wrap items-center justify-end gap-2 md:flex-col md:items-stretch md:justify-center">
          <button
            type="button"
            class="inline-flex items-center justify-center gap-1.5 rounded-xl border border-matte-lilac/90 bg-matte-dust/50 px-3 py-2 text-xs font-medium text-charcoal shadow-sm transition hover:border-pastel-lavender hover:bg-white disabled:opacity-50"
            :disabled="loadingEdit"
            @click="openEdit(u.university_id)"
          >
            <Pencil class="h-3.5 w-3.5" stroke-width="2" aria-hidden="true" />
            Редактировать
          </button>
          <a
            :href="`/universities/${u.university_id}`"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center justify-center gap-1.5 rounded-xl border border-matte-lilac/80 bg-white/70 px-3 py-2 text-xs font-medium text-charcoal/80 shadow-sm transition hover:border-pastel-lavender"
          >
            <ExternalLink class="h-3.5 w-3.5" stroke-width="2" aria-hidden="true" />
            На сайте
          </a>
          <button
            type="button"
            class="inline-flex items-center justify-center gap-1.5 rounded-xl border border-red-200/90 bg-red-50/50 px-3 py-2 text-xs font-medium text-red-800 shadow-sm transition hover:bg-red-50"
            @click="openDeleteConfirm(u)"
          >
            <Trash2 class="h-3.5 w-3.5" stroke-width="2" aria-hidden="true" />
            Удалить
          </button>
        </div>
      </div>
    </div>

    <AdminUniversityFormModal
      :open="modalOpen"
      :mode="modalMode"
      :initial="modalInitial"
      :cities="cities"
      @update:open="modalOpen = $event"
      @saved="onModalSaved"
    />

    <Teleport to="body">
      <div
        v-if="deleteTarget"
        class="fixed inset-0 z-[85] flex items-end justify-center p-4 sm:items-center sm:p-6"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-uni-title"
        aria-describedby="delete-uni-desc"
      >
        <div class="absolute inset-0 bg-charcoal/45 backdrop-blur-[3px]" aria-hidden="true" @click="cancelDelete" />
        <div
          class="relative w-full max-w-md overflow-hidden rounded-2xl border border-matte-lilac/95 bg-[#f3f0f8] shadow-soft"
        >
          <div class="flex gap-3 border-b border-matte-lilac/80 bg-matte-dust/50 px-5 py-4">
            <div
              class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100/90 text-amber-800"
              aria-hidden="true"
            >
              <AlertTriangle class="h-5 w-5" stroke-width="2" />
            </div>
            <div class="min-w-0 flex-1 pt-0.5">
              <h2 id="delete-uni-title" class="text-base font-semibold text-charcoal">Удалить вуз?</h2>
              <p id="delete-uni-desc" class="mt-1 text-sm leading-relaxed text-charcoal/70">
                Запись будет удалена из таблицы
                <span class="font-mono text-xs text-charcoal/80">dwh.dim_university</span>
                . Это действие необратимо. Если на вуз ссылаются данные витрины или факты, удаление будет отклонено
                базой данных.
              </p>
              <p class="mt-2 rounded-xl border border-matte-lilac/80 bg-white/60 px-3 py-2 text-sm font-medium text-charcoal">
                {{ deleteTarget.university_name }}
              </p>
            </div>
            <button
              type="button"
              class="shrink-0 rounded-xl p-2 text-charcoal/45 transition hover:bg-matte-lilac/60 hover:text-charcoal"
              aria-label="Закрыть"
              @click="cancelDelete"
            >
              <X class="h-5 w-5" stroke-width="2" />
            </button>
          </div>
          <div class="flex flex-wrap justify-end gap-2 px-5 py-4">
            <button
              type="button"
              class="rounded-xl border border-matte-lilac/90 bg-white/80 px-4 py-2.5 text-sm font-medium text-charcoal/80 shadow-sm transition hover:border-pastel-lavender hover:bg-white"
              :disabled="deleteSubmitting"
              @click="cancelDelete"
            >
              Отмена
            </button>
            <button
              type="button"
              class="rounded-xl border border-red-300/90 bg-red-100/80 px-4 py-2.5 text-sm font-semibold text-red-900 shadow-sm transition hover:bg-red-100 disabled:opacity-50"
              :disabled="deleteSubmitting"
              @click="confirmDelete"
            >
              {{ deleteSubmitting ? "Удаление…" : "Удалить навсегда" }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>
