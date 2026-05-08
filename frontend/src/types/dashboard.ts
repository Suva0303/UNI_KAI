export type DashboardKpis = {
  avg_salary: number;
  employment_rate: number;
  graduates_count: number;
  top_employer: string | null;
};

export type SalaryDynamicPoint = { year: number; avg_salary: number };

export type EmploymentYearPoint = {
  year: number;
  employed_percent: number;
  unemployed_percent: number;
};

export type IndustrySlice = {
  industry_name: string;
  count: number;
  percentage: number;
};

export type UniversityComparisonRow = {
  university_id: number;
  university_name: string;
  employment_total_percent: number;
  employment_specialty_percent: number;
  graduates_count: number;
  avg_salary: number;
};

export type GeographyRow = {
  region_name: string;
  graduates_count: number;
  employment_rate: number;
};

export type EducationLevelOption = { level_id: number | null; label: string };

export type RegionOption = { region_id: number; region_name: string };

export type ProgramOption = { program_code: string; program_name: string };

export type UniversityOption = {
  university_id: number;
  university_name: string;
  university_code?: string;
  city_name?: string;
  rating?: number;
};

export type UniversitiesMeta = {
  universities_total: number;
  universities_with_mart?: number;
  data_year: number;
  education_levels?: EducationLevelOption[];
};

export type UniversityListRow = {
  university_id: number;
  university_name: string;
  city_name: string;
  rating: number | null;
  avg_salary: number;
  employment_rate: number;
  employed_count?: number;
  specialty_rate?: number;
  composite_score?: number;
  region_name: string;
};

export type UniversityProfile = {
  university_id: number;
  university_code: string | null;
  university_name: string;
  foundation_year: number | null;
  rating: number | null;
  website: string | null;
  description: string | null;
  logo_url?: string | null;
  city_name: string;
  region_name: string | null;
  graduates_count: number;
  avg_salary: number;
  employment_rate: number;
  specialty_rate: number;
};

export type ProgramAnalyticsRow = {
  program_code: string;
  program_name: string;
  avg_salary: number;
  employment_rate: number;
  specialty_rate: number;
  salary_by_year: SalaryDynamicPoint[];
};

export type ProgramEmployerRow = {
  company_name: string;
  graduates_count: number;
};

export type AdminCityOption = { city_id: number; city_name: string; region_name: string };

export type AdminUniversityDetail = {
  university_id: number;
  university_code: string;
  university_name: string;
  city_id: number | null;
  city_name: string | null;
  foundation_year: number | null;
  rating: number | null;
  website: string | null;
  description: string | null;
  logo_url: string | null;
};
