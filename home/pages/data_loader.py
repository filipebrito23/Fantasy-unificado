from pathlib import Path
import pandas as pd

SEASONS = ["26_27", "27_28", "28_29", "29_30"]
SALARY_COLS = [f"salarie_{s}" for s in SEASONS]
OPTION_COLS = [f"option_{s}" for s in SEASONS]
FINE_COLS = [f"fine_{s}" for s in SEASONS]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _to_string(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df


def load_workbook_data(file_path: str | Path = "roster.xlsx") -> dict[str, pd.DataFrame]:
    path = Path(file_path)
    sheets = pd.read_excel(path, sheet_name=None)
    data = {name: _normalize_columns(df) for name, df in sheets.items()}

    required = ["players", "teams", "roster", "development", "picks", "fines"]
    missing = [name for name in required if name not in data]
    if missing:
        raise ValueError(f"Abas obrigatórias ausentes: {', '.join(missing)}")

    data["players"] = _to_numeric(data["players"], ["player_id"])
    data["teams"] = _to_numeric(data["teams"], ["team_id"])
    data["roster"] = _to_numeric(data["roster"], ["team_id", "player_id", "pos_order", *SALARY_COLS])
    data["development"] = _to_numeric(data["development"], ["team_id", "player_id", "order", *SALARY_COLS])
    data["picks"] = _to_numeric(data["picks"], ["original_team_pick_id", "round", "year", "current_team_owner_id"])
    data["fines"] = _to_numeric(data["fines"], ["team_id", *FINE_COLS])

    data["roster"] = _to_string(data["roster"], OPTION_COLS)
    data["development"] = _to_string(data["development"], OPTION_COLS)
    data["picks"] = _to_string(data["picks"], ["pick_id"])
    data["fines"] = _to_string(data["fines"], ["notes"])

    if "Jogador" in data["roster"].columns:
        data["roster"] = data["roster"].drop(columns=["Jogador"])

    return data
