<script setup lang="ts">
import axios from "axios";
import { onMounted, ref, watch } from "vue";
import { api } from "../../services/api";
import { useFilterStore } from "../../stores/filterStore";
import type {
  DashboardKpis,
  EducationLevelOption,
  EmploymentYearPoint,
  GeographyRow,
  IndustrySlice,
  ProgramOption,
  RegionOption,
  SalaryDynamicPoint,
  UniversitiesMeta,
  UniversityComparisonRow,
  UniversityOption,
} from "../../types/dashboard";
import ChartsTabPanel from "../../components/dashboard/ChartsTabPanel.vue";
import DashboardFilters from "../../components/dashboard/DashboardFilters.vue";
import GeographyMap from "../../components/dashboard/GeographyMap.vue";
import KpiCards from "../../components/dashboard/KpiCards.vue";

const FALLBACK_EDUCATION_LEVELS: EducationLevelOption[] = [
  { level_id: null, label: "Все" },
  { level_id: 1, label: "Бакалавриат" },
  { level_id: 2, label: "Специалитет" },
  { level_id: 3, label: "Магистратура" },
  { level_id: 4, label: "Аспирантура" },
  { level_id: 5, label: "Докторантура" },
];

function parseEducationLevelsFromMeta(payload: unknown): EducationLevelOption[] {
  if (!payload || typeof payload !== "object") return [];
  const d = payload as Record<string, unknown>;
  const raw = d.education_levels ?? d.educationLevels;
  if (!Array.isArray(raw)) return [];
  const out: EducationLevelOption[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const x = item as Record<string, unknown>;
    const label = x.label;
    if (typeof label !== "string" || !label.trim()) continue;
    const lid = x.level_id ?? x.levelId;
    const level_id =
      lid === null || lid === undefined || lid === "" ? null : Number(lid);
    if (level_id !== null && Number.isNaN(level_id)) continue;
    out.push({ level_id, label: label.trim() });
  }
  return out;
}

const filterStore = useFilterStore();

const educationLevels = ref<EducationLevelOption[]>([]);
const regions = ref<RegionOption[]>([]);
const programs = ref<ProgramOption[]>([]);
const universities = ref<UniversityOption[]>([]);
const graduationYears = ref<number[]>([]);
const loadingMeta = ref(false);
const metaError = ref<string | null>(null);

const kpis = ref<DashboardKpis | null>(null);
const loadingKpis = ref(false);
const kpisError = ref<string | null>(null);

const salaryData = ref<SalaryDynamicPoint[]>([]);
const employmentData = ref<EmploymentYearPoint[]>([]);
const industryData = ref<IndustrySlice[]>([]);
const loadingCharts = ref(false);
const chartsError = ref<string | null>(null);

const geographyRows = ref<GeographyRow[]>([]);
const loadingGeo = ref(false);
const geoError = ref<string | null>(null);

const activeTab = ref("salary");
const comparisonSlots = ref<(number | null)[]>([null, null]);
const comparisonRows = ref<UniversityComparisonRow[]>([]);
const loadingComparison = ref(false);
const comparisonError = ref<string | null>(null);

function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "detail" in d) {
      const det = (d as { detail: unknown }).detail;
      if (typeof det === "string") return det;
      if (Array.isArray(det))
        return det.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join("; ");
    }
    return err.message || "Ошибка запроса к серверу";
  }
  return "Неизвестная ошибка";
}

function comparisonQueryString(): string {
  const p = new URLSearchParams();
  const q = filterStore.queryParams;
  if (q.level_id != null) p.set("level_id", String(q.level_id));
  if (q.graduation_year != null) p.set("graduation_year", String(q.graduation_year));
  if (q.region_id != null) p.set("region_id", String(q.region_id));
  if (q.program_code != null) p.set("program_code", q.program_code);
  for (const id of comparisonIdsForApi()) p.append("university_ids", String(id));
  return p.toString();
}

function comparisonIdsForApi(): number[] {
  return comparisonSlots.value.filter((x): x is number => x != null);
}

async function loadMeta() {
  loadingMeta.value = true;
  metaError.value = null;
  educationLevels.value = [];
  regions.value = [];
  programs.value = [];
  universities.value = [];
  graduationYears.value = [];

  const parts = await Promise.allSettled([
    api.get<RegionOption[]>("/api/public/regions"),
    api.get<ProgramOption[]>("/api/public/programs"),
    api.get<{ items: UniversityOption[] }>("/api/public/universities-catalog"),
    api.get<number[]>("/api/public/graduation-years"),
    api.get<UniversitiesMeta>("/api/public/universities-meta"),
  ]);

  const errs: string[] = [];
  if (parts[0].status === "fulfilled") regions.value = parts[0].value.data;
  else errs.push(`Регионы: ${formatApiError(parts[0].reason)}`);

  if (parts[1].status === "fulfilled") programs.value = parts[1].value.data;
  else errs.push(`Направления: ${formatApiError(parts[1].reason)}`);

  if (parts[2].status === "fulfilled") {
    const raw = parts[2].value.data.items ?? [];
    universities.value = raw.map((u) => ({
      ...u,
      university_id: Number(u.university_id),
      rating: u.rating == null ? undefined : Number(u.rating),
    }));
  } else errs.push(`Вузы: ${formatApiError(parts[2].reason)}`);

  if (parts[3].status === "fulfilled") graduationYears.value = parts[3].value.data ?? [];
  else errs.push(`Годы выпуска: ${formatApiError(parts[3].reason)}`);

  let educationLevelsFromMeta = false;
  if (parts[4].status === "fulfilled") {
    const parsed = parseEducationLevelsFromMeta(parts[4].value.data);
    if (parsed.length > 0) {
      educationLevels.value = parsed;
      educationLevelsFromMeta = true;
    } else {
      educationLevels.value = [...FALLBACK_EDUCATION_LEVELS];
    }
  } else {
    educationLevels.value = [...FALLBACK_EDUCATION_LEVELS];
    errs.push(`Сводка по вузам (мета): ${formatApiError(parts[4].reason)}`);
  }

  if (!educationLevelsFromMeta) {
    try {
      const { data } = await api.get<EducationLevelOption[]>("/api/public/education-levels");
      if (Array.isArray(data) && data.length > 0) educationLevels.value = data;
    } catch {
      /* уже FALLBACK или копия */
    }
  }

  if (errs.length) {
    metaError.value = errs.join(" ");
  }
  loadingMeta.value = false;
}

async function loadKpis() {
  loadingKpis.value = true;
  kpisError.value = null;
  try {
    const { data } = await api.get<DashboardKpis>("/api/public/dashboard/kpis", { params: filterStore.queryParams });
    kpis.value = data;
  } catch (e) {
    kpisError.value = `Не удалось загрузить показатели KPI: ${formatApiError(e)}`;
    kpis.value = null;
  } finally {
    loadingKpis.value = false;
  }
}

async function loadCharts() {
  loadingCharts.value = true;
  chartsError.value = null;
  const params = filterStore.queryParams;
  const endpoints = [
    ["salary", "/api/public/dashboard/salary-dynamics"],
    ["employment", "/api/public/dashboard/employment-rate-by-year"],
    ["industry", "/api/public/dashboard/industry-distribution"],
  ] as const;
  const results = await Promise.allSettled(
    endpoints.map(([, url]) => api.get(url, { params })),
  );
  salaryData.value = [];
  employmentData.value = [];
  industryData.value = [];
  const errs: string[] = [];
  results.forEach((r, i) => {
    const [key] = endpoints[i];
    if (r.status === "fulfilled") {
      const data = r.value.data as SalaryDynamicPoint[] | EmploymentYearPoint[] | IndustrySlice[];
      if (key === "salary") salaryData.value = data as SalaryDynamicPoint[];
      if (key === "employment") employmentData.value = data as EmploymentYearPoint[];
      if (key === "industry") industryData.value = data as IndustrySlice[];
    } else {
      errs.push(`${endpoints[i][1]}: ${formatApiError(r.reason)}`);
    }
  });
  if (errs.length) {
    chartsError.value = `Не удалось загрузить часть графиков. ${errs.join(" ")}`;
  }
  loadingCharts.value = false;
}

async function loadGeography() {
  loadingGeo.value = true;
  geoError.value = null;
  try {
    const { data } = await api.get<GeographyRow[]>("/api/public/dashboard/geography", { params: filterStore.queryParams });
    geographyRows.value = data;
  } catch {
    geoError.value = "Не удалось загрузить данные по регионам.";
    geographyRows.value = [];
  } finally {
    loadingGeo.value = false;
  }
}

async function loadComparison() {
  const ids = comparisonIdsForApi();
  if (ids.length === 0) {
    comparisonRows.value = [];
    comparisonError.value = null;
    return;
  }
  loadingComparison.value = true;
  comparisonError.value = null;
  try {
    const qs = comparisonQueryString();
    const { data } = await api.get<UniversityComparisonRow[]>(`/api/public/dashboard/university-comparison?${qs}`);
    comparisonRows.value = data;
  } catch {
    comparisonError.value = "Не удалось загрузить сравнение вузов.";
    comparisonRows.value = [];
  } finally {
    loadingComparison.value = false;
  }
}

async function refreshDashboard() {
  await Promise.all([loadKpis(), loadCharts(), loadGeography(), loadComparison()]);
}

watch(
  () => filterStore.queryParams,
  () => {
    void refreshDashboard();
  },
  { deep: true },
);

watch(
  comparisonSlots,
  () => {
    void loadComparison();
  },
  { deep: true },
);

onMounted(async () => {
  await loadMeta();
  await refreshDashboard();
});
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold leading-tight text-charcoal">Аналитический дашборд</h1>

    <p v-if="metaError" class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{{ metaError }}</p>

    <DashboardFilters
      :education-levels="educationLevels"
      :regions="regions"
      :programs="programs"
      :universities="universities"
      :graduation-years="graduationYears"
      :loading-meta="loadingMeta"
    />

    <KpiCards :kpis="kpis" :loading="loadingKpis" :error="kpisError" />

    <ChartsTabPanel
      v-model:comparison-slots="comparisonSlots"
      v-model:active-tab="activeTab"
      :salary-data="salaryData"
      :employment-data="employmentData"
      :industry-data="industryData"
      :comparison-rows="comparisonRows"
      :universities="universities"
      :loading-charts="loadingCharts"
      :charts-error="chartsError"
      :loading-comparison="loadingComparison"
      :comparison-error="comparisonError"
    />

    <GeographyMap :rows="geographyRows" :loading="loadingGeo" :error="geoError" />
  </section>
</template>
