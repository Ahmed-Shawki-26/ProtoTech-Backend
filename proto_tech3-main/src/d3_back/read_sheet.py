import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

# Define the scope
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Path to your credentials file
creds = ServiceAccountCredentials.from_json_keyfile_name("credntials.json", scope)

# Authorize the client
client = gspread.authorize(creds)

# Open the spreadsheet by URL or title
spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1djgrDegWTqgDLFNyUB6_OvAsuyKDc5Ya37SFarWMLd4")

# Select sheet by name or index
worksheet = spreadsheet.get_worksheet(0)  # or spreadsheet.worksheet("Sheet1")

# Read as DataFrame
data = pd.DataFrame(worksheet.get_all_records())
print(data.columns)
print(data.head())
# ['Name', 'Brand', 'Color', 'Material', 'Storage Location',
#        'Loaded In Printer', 'Remaining (g)']     columns 
# avaliable_colorsdata.groupby('Material')['Color'].unique())