from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app_lib.fantasy_data_service import (
    get_neon_data_counts,
    load_fantasy_data_from_neon,
)


def main():
    print("=" * 70)
    print("PNBC-04A — Diagnóstico de leitura Neon")
    print("=" * 70)

    counts = get_neon_data_counts()

    for key, count in counts.items():
        print(f"{key}: {count}")

    print()
    print("=" * 70)
    print("AMOSTRA DE COLUNAS")
    print("=" * 70)

    data = load_fantasy_data_from_neon()

    for key, df in data.items():
        print(f"\n[{key}]")
        print(f"Colunas: {list(df.columns)}")
        print(df.head(3).to_string(index=False))


if __name__ == "__main__":
    main()