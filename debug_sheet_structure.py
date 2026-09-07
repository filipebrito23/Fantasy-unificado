"""
Debug: Ver estrutura das planilhas
"""

from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
URLS_FILE = Path(__file__).parent / "url-2.txt"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def extract_spreadsheet_id(url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"URL invalida: {url}")


import re

# Autenticacao
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
service = build("sheets", "v4", credentials=creds)

# Ler primeira URL
with open(URLS_FILE, "r", encoding="utf-8") as f:
    first_line = f.readline().strip()

url = first_line.split(" - ", 1)[1]
spreadsheet_id = extract_spreadsheet_id(url)

print(f"Analisando planilha: {spreadsheet_id}\n")

# Obter metadata
spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
sheets = spreadsheet.get("sheets", [])

for sheet in sheets[:1]:  # Apenas primeira aba
    sheet_name = sheet["properties"]["title"]
    print(f"Aba: {sheet_name}")
    
    # Ler linhas 1-20
    range_name = f"{sheet_name}!A1:Z20"
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    values = result.get("values", [])
    
    print(f"Total de linhas lidas: {len(values)}\n")
    
    for i, row in enumerate(values[:20], start=1):
        print(f"Linha {i}: {row}")