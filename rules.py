from data_loader import FINE_COLS


def get_salary_penalty_rate(salary: float) -> float:
    if salary is None:
        return 0.0
    if salary < 500_000:
        return 0.0
    if salary <= 5_000_000:
        return 0.15
    if salary <= 10_000_000:
        return 0.20
    if salary <= 15_000_000:
        return 0.25
    return 0.30


def empty_fines_row(team_id: int) -> dict:
    row = {"team_id": team_id}
    for col in FINE_COLS:
        row[col] = 0.0
    row["notes"] = ""
    return row
