<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useFilterStore } from "../../stores/filterStore";
import type { EducationLevelOption, ProgramOption, RegionOption, UniversityOption } from "../../types/dashboard";
import SearchableSelect, { type SelectOption } from "./SearchableSelect.vue";

const props = defineProps<{
  educationLevels: EducationLevelOption[];
  regions: RegionOption[];
  programs: ProgramOption[];
  universities: UniversityOption[];
  graduationYears: number[];
  loadingMeta?: boolean;
}>();

const filterStore = useFilterStore();
const {
  draftEducationLevelId,
  draftGraduationYear,
  draftRegionId,
  draftUniversityId,
  draftProgramCode,
} = storeToRefs(filterStore);

function setEducationLevel(v: number | null) {
  draftEducationLevelId.value = v;
}

function chipClass(active: boolean) {
  return [
    "rounded-full px-2.5 py-0.5 text-xs font-medium leading-tight transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-[#8b7bb8]",
    active
      ? "bg-gradient-to-r from-pastel-lavender via-pastel-blue/90 to-pastel-mint text-charcoal shadow-sm ring-1 ring-charcoal/15"
      : "border border-charcoal/10 bg-ivory text-charcoal/80 hover:border-charcoal/20 hover:bg-ivory-light",
  ];
}

const yearOptions = computed<SelectOption[]>(() => [
  { value: null, label: "Все годы" },
  ...props.graduationYears.map((y) => ({ value: y, label: String(y) })),
]);

const regionOptions = computed<SelectOption[]>(() => [
  { value: null, label: "Все регионы" },
  ...props.regions.map((r) => ({ value: r.region_id, label: r.region_name })),
]);

const universityOptions = computed<SelectOption[]>(() => [
  { value: null, label: "Все вузы" },
  ...props.universities.map((u) => ({
    value: u.university_id,
    label: [u.university_name, u.city_name ? `(${u.city_name})` : null].filter(Boolean).join(" "),
  })),
]);

const programOptions = computed<SelectOption[]>(() => [
  { value: null, label: "Все направления" },
  ...props.programs.map((p) => ({
    value: p.program_code,
    label: `${p.program_code} — ${p.program_name ?? ""}`.trim(),
  })),
]);
</script>

<template>
  <div
    class="rounded-xl border border-charcoal/5 bg-gradient-to-br from-white via-ivory-light to-pastel-lavender/30 p-3 shadow-soft"
  >
    <div class="mb-2 flex flex-col gap-0.5 border-b border-charcoal/10 pb-2 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 class="text-sm font-semibold leading-tight text-charcoal">Фильтры дашборда</h2>
        <p class="mt-0.5 text-[11px] leading-snug text-charcoal/60">Выберите значения и нажмите «Применить фильтр»</p>
      </div>
    </div>

    <div class="mb-3">
      <p class="mb-1 text-[11px] font-medium uppercase leading-tight tracking-wide text-charcoal/55">Уровень образования</p>
      <div class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="opt in props.educationLevels"
          :key="String(opt.level_id ?? 'all')"
          type="button"
          :class="chipClass(draftEducationLevelId === opt.level_id)"
          :disabled="loadingMeta"
          @click="setEducationLevel(opt.level_id)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <div class="flex flex-col gap-0.5">
        <label class="text-[11px] font-medium leading-tight text-charcoal/70">Год</label>
        <SearchableSelect
          :model-value="draftGraduationYear"
          :options="yearOptions"
          placeholder="Все годы"
          border-class="border-pastel-lavender"
          :disabled="loadingMeta"
          @update:model-value="draftGraduationYear = $event as number | null"
        />
      </div>
      <div class="flex flex-col gap-0.5">
        <label class="text-[11px] font-medium leading-tight text-charcoal/70">Регион</label>
        <SearchableSelect
          :model-value="draftRegionId"
          :options="regionOptions"
          placeholder="Все регионы"
          border-class="border-pastel-blue"
          :disabled="loadingMeta"
          @update:model-value="draftRegionId = $event as number | null"
        />
      </div>
      <div class="flex flex-col gap-0.5">
        <label class="text-[11px] font-medium leading-tight text-charcoal/70">Вуз</label>
        <SearchableSelect
          :model-value="draftUniversityId"
          :options="universityOptions"
          placeholder="Все вузы"
          border-class="border-pastel-mint"
          :disabled="loadingMeta"
          @update:model-value="draftUniversityId = $event as number | null"
        />
      </div>
      <div class="flex flex-col gap-0.5">
        <label class="text-[11px] font-medium leading-tight text-charcoal/70">Направление подготовки</label>
        <SearchableSelect
          :model-value="draftProgramCode"
          :options="programOptions"
          placeholder="Все направления"
          border-class="border-pastel-peach"
          :disabled="loadingMeta"
          @update:model-value="draftProgramCode = $event as string | null"
        />
      </div>
    </div>

    <div class="mt-2.5 flex flex-wrap items-center justify-end gap-2">
      <button
        type="button"
        class="rounded-lg border border-charcoal/15 bg-white px-4 py-1.5 text-xs font-semibold text-charcoal/85 shadow-sm transition hover:border-charcoal/25 hover:bg-ivory focus:outline-none focus-visible:ring-2 focus-visible:ring-charcoal/20 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-55"
        :disabled="loadingMeta"
        @click="filterStore.resetFilters()"
      >
        Сбросить фильтры
      </button>
      <button
        type="button"
        class="rounded-lg bg-gradient-to-r from-[#7c6cf0] via-[#e879a9] to-[#f0a04b] px-4 py-1.5 text-xs font-semibold text-white shadow shadow-charcoal/10 transition hover:brightness-105 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7c6cf0] focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-55"
        :disabled="loadingMeta"
        @click="filterStore.applyFilters()"
      >
        Применить фильтр
      </button>
    </div>
  </div>
</template>
