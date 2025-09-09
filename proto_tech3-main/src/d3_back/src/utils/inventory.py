# d3_back/src/utils/inventory.py

import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from src.d3_back.src.config import settings

def get_inventory_data() -> pd.DataFrame:
    """
    Fetches and prepares the inventory data from Google Sheets.
    
    Raises:
        RuntimeError: If credentials are not found or connection fails.
    """
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            settings.GOOGLE_SHEETS_CREDS_FILE, 
            settings.GOOGLE_SHEETS_SCOPE
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(settings.GOOGLE_SHEETS_URL)
        worksheet = spreadsheet.get_worksheet(0)
        
        data = pd.DataFrame(worksheet.get_all_records())
        
        # Pre-process the data for consistency
        if 'Material' in data.columns:
            data['Material_Short'] = data['Material'].apply(lambda x: str(x).split(' ')[0].upper())
        if 'Color' in data.columns:
            data['Color_Upper'] = data['Color'].str.upper()
        
        return data
    except FileNotFoundError:
        raise RuntimeError(f"The '{settings.GOOGLE_SHEETS_CREDS_FILE}' file was not found.")
    except Exception as e:
        raise RuntimeError(f"Could not connect to or process Google Sheets data: {e}")