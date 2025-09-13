# d3_back/src/config/settings.py

# Material densities in g/cm^3
MATERIAL_DENSITIES = {
    "ABS": 1.05,
    "PLA": 1.24,
    "TPU": 1.18,
    "PETG": 1.30
}

# Price per gram in EGP for each material
PRICE_PER_GRAM_EGP = {
    "TPU": 5.0,
    "ABS": 2.5,
    "PLA": 2.5,
    "PETG": 2.5
}

# Google Sheets configuration
GOOGLE_SHEETS_SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GOOGLE_SHEETS_CREDS_FILE = "gdrive_credntials.json"
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/1djgrDegWTqgDLFNyUB6_OvAsuyKDc5Ya37SFarWMLd4"