from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    token: str


class DashboardStats(BaseModel):
    universities_total: int
    graduates_total: int
    companies_total: int
    employments_total: int
    last_csv_load: datetime | None
    last_events: list[dict]


class UniversityBase(BaseModel):
    university_code: str
    university_name: str
    city_id: int
    foundation_year: int | None = None
    rating: float | None = None
    website: str | None = None
    description: str | None = None
    logo_url: str | None = None

    @field_validator("website", "logo_url", "description", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v


class UniversityCreate(UniversityBase):
    pass


class UniversityUpdate(UniversityBase):
    pass


class UniversityOut(UniversityBase):
    university_id: int
    city_name: str | None = None
    city_id: int | None = None


class PaginatedUniversities(BaseModel):
    items: list[UniversityOut]
    total: int
    page: int
    page_size: int


class ImportPayload(BaseModel):
    rows: list[dict]


class GraduateManualRow(BaseModel):
    """Одна строка для загрузки в staging (совпадает с колонками CSV)."""

    local_student_id: str = Field(min_length=1)
    university_code: str = Field(min_length=1)
    graduation_year: str | int
    program_code: str | None = None
    program_name: str | None = None
    specialization_edu_code: str | None = None
    specialization_edu_name: str | None = None
    birth_year: str | int | None = None
    gender: str | None = None
    is_employed: str | bool | int | float | None = None
    company_name: str | None = None
    inn: str | None = None
    industry_name: str | None = None
    position: str | None = None
    salary: str | None = None
    specialization_work_code: str | None = None
    specialization_work_name: str | None = None
    hire_date: str | None = None
    works_by_specialty: str | bool | int | float | None = None

    @field_validator(
        "program_code",
        "program_name",
        "specialization_edu_code",
        "specialization_edu_name",
        "birth_year",
        "gender",
        "is_employed",
        "works_by_specialty",
        "company_name",
        "inn",
        "industry_name",
        "position",
        "salary",
        "specialization_work_code",
        "specialization_work_name",
        "hire_date",
        mode="before",
    )
    @classmethod
    def empty_str_optional(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @field_validator("local_student_id", "university_code", mode="before")
    @classmethod
    def strip_required(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("graduation_year", mode="before")
    @classmethod
    def strip_grad_year(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class EtlSummary(BaseModel):
    staging_rows: int = 0
    fact_rows: int = 0
    mart_rows: int = 0


class ImportResult(BaseModel):
    task_id: str
    inserted: int
    errors: list[str]
    etl: EtlSummary | None = None


class StudentListResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int


class SeedDashboardDemoResponse(BaseModel):
    ok: bool
    inserted_mart_rows: int | None = None
    universities: int | None = None
    notes: list[str] = []
    error: str | None = None


class ArticleCreate(BaseModel):
    title: str = Field(min_length=1)
    excerpt: str | None = None
    content: str | None = None
    category: str | None = None
    image_url: str | None = None

    @field_validator("excerpt", "content", "category", "image_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v


class ArticleOut(BaseModel):
    id: int
    title: str
    excerpt: str | None = None
    content: str | None = None
    category: str | None = None
    image_url: str | None = None
    created_at: datetime | None = None
