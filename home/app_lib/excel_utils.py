# excel_utils.py

import pandas as pd


def get_next_id(df: pd.DataFrame, col: str, start: int = 1) -> int:
    if df.empty or col not in df.columns:
        return start
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return int(s.max()) + 1 if not s.empty else start


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out = out.where(pd.notna(out), None)
    return out

def make_unique_columns(columns) -> list[str]:
    seen = {}
    new_cols = []

    for col in columns:
        base = "" if col is None else str(col).strip()
        if base not in seen:
            seen[base] = 0
            new_cols.append(base)
        else:
            seen[base] += 1
            new_cols.append(f"{base}__dup{seen[base]}")
    return new_cols


def ensure_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    out = df.copy()
    out.columns = make_unique_columns(out.columns)
    return out


def find_sheet_name(wb, sheet_name: str) -> str | None:
    target = str(sheet_name).strip().lower()

    for existing_name in wb.sheetnames:
        if str(existing_name).strip().lower() == target:
            return existing_name

    aliases = {
        "transaction_items": ["transaction_items", "transactionitems"],
        "transactionitems": ["transaction_items", "transactionitems"],
        "transactions": ["transactions", "transaction"],
        "roster": ["roster"],
        "development": ["development", "dev"],
        "picks": ["picks", "pick"],
    }

    valid_names = aliases.get(target, [target])

    for existing_name in wb.sheetnames:
        normalized_existing = str(existing_name).strip().lower()
        if normalized_existing in valid_names:
            return existing_name

    return None


def load_sheet_df(wb, sheet_name: str) -> pd.DataFrame:
    if sheet_name not in wb.sheetnames:
        return pd.DataFrame()

    ws = wb[sheet_name]
    rows = list(ws.values)
    if not rows:
        return pd.DataFrame()

    headers = make_unique_columns(rows[0])
    df = pd.DataFrame(rows[1:], columns=headers)
    return ensure_unique_columns(df)


def save_sheet_df(wb, sheet_name: str, df: pd.DataFrame):
    real_name = find_sheet_name(wb, sheet_name)

    if real_name in wb.sheetnames:
        ws = wb[real_name]
        wb.remove(ws)

    ws = wb.create_sheet(sheet_name)

    if df.empty:
        return

    df2 = normalize_df(df)
    df2 = df2.astype(object).where(pd.notna(df2), None)

    ws.append(list(df2.columns))
    for _, row in df2.iterrows():
        ws.append([None if pd.isna(v) else v for v in row.tolist()])