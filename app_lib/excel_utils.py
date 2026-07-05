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
    real_name = find_sheet_name(wb, sheet_name)
    if real_name is None:
        return pd.DataFrame()

    ws = wb[real_name]
    rows = list(ws.values)

    if not rows:
        return pd.DataFrame()

    header = rows[0]
    data_rows = rows[1:]

    if header is None:
        return pd.DataFrame()

    return pd.DataFrame(data_rows, columns=header)


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