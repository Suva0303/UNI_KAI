from pydantic import BaseModel


class PublicStats(BaseModel):
    universities_total: int
    avg_salary: float
    employment_rate: float
    graduates_last_year: int
    top_universities_salary: list[dict]
    regional_employment: list[dict]
