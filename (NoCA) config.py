import os
# <> File Paths <> #
key = os.environ.get('NoCA_Key')
if not key:
    raise RuntimeError('NoCA_Key environment variable not found')
travelers_sheet = "current_travelers.csv"
script_path = "OU_Mover.ps1"
log_path = 'NoCA_log.log'
OU_csv = 'OU.csv'
gcds = 'Azure-GADS.exe'
# <> Values <> #
spreadsheet_id = 'id'
sheet_id = 'id'
scope = ['https://www.googleapis.com/auth/spreadsheets']
range = 'Trigger!A2'
input = 'USER_ENTERED'
cell_range = 'sheetname!A1:L1000'
date_format = '%m/%d/%Y'
domains = ['staffdomain', 'studentdomain']
