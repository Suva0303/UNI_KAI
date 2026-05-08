import { defineStore } from "pinia";
import { computed, ref } from "vue";

export type DashboardQueryParams = {
  level_id?: number;
  region_id?: number;
  university_id?: number;
  program_code?: string;
  graduation_year?: number;
};

export const useFilterStore = defineStore("dashboardFilters", () => {
  const educationLevelId = ref<number | null>(null);
  const graduationYear = ref<number | null>(null);
  const regionId = ref<number | null>(null);
  const universityId = ref<number | null>(null);
  const programCode = ref<string | null>(null);

  const draftEducationLevelId = ref<number | null>(null);
  const draftGraduationYear = ref<number | null>(null);
  const draftRegionId = ref<number | null>(null);
  const draftUniversityId = ref<number | null>(null);
  const draftProgramCode = ref<string | null>(null);

  const queryParams = computed((): DashboardQueryParams => {
    const p: DashboardQueryParams = {};
    if (educationLevelId.value != null) p.level_id = educationLevelId.value;
    if (graduationYear.value != null) p.graduation_year = graduationYear.value;
    if (regionId.value != null) p.region_id = regionId.value;
    if (universityId.value != null) p.university_id = universityId.value;
    if (programCode.value != null && programCode.value !== "") p.program_code = programCode.value;
    return p;
  });

  function applyFilters() {
    educationLevelId.value = draftEducationLevelId.value;
    graduationYear.value = draftGraduationYear.value;
    regionId.value = draftRegionId.value;
    universityId.value = draftUniversityId.value;
    programCode.value = draftProgramCode.value;
  }

  function resetFilters() {
    educationLevelId.value = null;
    graduationYear.value = null;
    regionId.value = null;
    universityId.value = null;
    programCode.value = null;
    draftEducationLevelId.value = null;
    draftGraduationYear.value = null;
    draftRegionId.value = null;
    draftUniversityId.value = null;
    draftProgramCode.value = null;
  }

  return {
    educationLevelId,
    graduationYear,
    regionId,
    universityId,
    programCode,
    draftEducationLevelId,
    draftGraduationYear,
    draftRegionId,
    draftUniversityId,
    draftProgramCode,
    queryParams,
    applyFilters,
    resetFilters,
  };
});
