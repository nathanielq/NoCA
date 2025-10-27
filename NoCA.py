import csv
import os
import subprocess
import sys
import pandas as pd
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# <> Set the time <> #
now = datetime.now()

# <> Logging <> #
log_path = 'PATH_TO_LOG_FILE'
sys.stdout = open(log_path, 'a')
sys.stderr = sys.stdout
print(f'\nStarting NoCA at {todays_date}')

# <> Authenticate with Google Sheets API <> #
def Authenticate():
    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPE) #if token.json exists pull credentials from that file to generate creds
    if not creds or not creds.valid: #if creds were not generated from token, or creds is no longer valid check a few instances of what causes that
        if creds and creds.expired and creds.refresh_token: #if creds.json exists but is expired refresh the token
            creds.refresh(Request())
        else: #if creds is blank token did not have the necessary info from Credentials.json and needs to be generated via below command
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPE) #CREDENTIALS is a json file pulled from the project file in Google Cloud Platform
            creds = flow.run_local_server(port=0) #im not gonna even pretend to fully understand this line :^)
        with open(TOKEN, 'w') as token: #write the newly generated creds to Token.json to speed up this process if call is done wihthin the expiration time
            token.write(creds.to_json())
    return creds

# <> Read in users from NoCA csv. Contains their full name, start-date, end-date, and Parent OU (either staff, or building if it is a student) <> #
def Get_Users(service):
    cell_range = 'Form Responses 1!A1:F250' #sheet name and it's range of cells available
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id,range=cell_range).execute() #google module function to grab the contents of the spreadsheet
    values = result.get('values', []) # <> parse the output into just the cell values
    headers = values[0] #first row ['email address', 'departure date', 'return date']
    users = [dict(zip(headers,row)) for row in values[1:]] #convert the list of rows (lists) to a list of dicts. zip combines the headers and rows and casts as a dict the for loop looks at all rows past 
    return users

# <> Get the users UPN by removing the email domain and the period <> #
def Get_SAM(email):
    email_split = email.split('@')[0] #grab first.last (split creates a list out of the original string at the point you split. 0 is the index of first.last)
    first_last = email_split.split('.') #same deal as above ['first','last']
    username = first_last[0] + ' ' + first_last[1] #combine the two items of the list with a space in between
    return username

# <> Once a user has been set to move back from NoCA this function runs to delete their form record from the Google sheet to keep it cleaner and reduce bugs <> #
def Delete_From_GSheet(delete_list):
    cell_range = 'Form Responses 1!A1:F250'
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id,range=cell_range).execute() #grab all values again
    values = result.get('values', [])
    try:
        # <> Find the rows containing the user emails <> #
        rows_to_delete = []
        for name in delete_list:
            for i ,row in enumerate(values[1:], start=2):
                if len(row) > 0 and name in row[1].strip().lower():
                    rows_to_delete.append(i - 1)
                    break
                
        # <> Iterate through the rows and delete from bottom up to prevent issues with shifting indices <> #
        for row in reversed(rows_to_delete):
            print(f'Index to delete: {row}')
            if row is not None:
                requests = [{
                    "deleteDimension": { #Google API command to delete content
                        "range": {
                            "sheetId": sheet_id, 
                            "dimension": "ROWS",
                            "startIndex": row,
                            "endIndex": row + 1
                        }
                    }            
                }]
                service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests}
            ).execute()
    except Exception as e:
        print(f'[ERROR]: {e}')

# <> Find a user to delete in the SAM CSV if not in GSheet <> #
def Delete_From_CSV(delete_list, df):
    new_df = df[~df['SAM'].isin(delete_list)] # only keeps rows where 'SAM' value is not in delete_list
    print(new_df)
    new_df.to_csv('PATH_TO_CSV', index=False, encoding='utf-8')

# <> Pull all existing users from the SAM csv for comparisons <> #
def Existing_Sam():
    existing_sam = []
    with open('PATH_TO_FILE', mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            existing_sam.append(row)
    
    return existing_sam

# <> OU in sam.csv can sometimes not be written correctly. This will attempt to correct it <> #
def Fix_OUs(user):
    print(f'User in Fix Ous: {user}')
    ou = ''
    try:
        df = pd.read_csv('PATH_TO_FILE', encoding='utf-8')
        ou = df.loc[df['Name'].str.lower() == user, 'OU'].item()
        print(ou)
        if 'No CA' in ou or ou == '':
            ou = 'OU not found'  
            print(f'Could not correct {user} Original OU')
    except Exception as e:
        print(f'Could not correct {user} Original OU: {e}')
    return ou

# <> Process the users for Active Directory <> #
def Move_Users(service, SAM_Sheet):
    sam_list = []
    delete_list = []
    # <> Get users <> #
    users = Get_Users(service) # Users from Google Sheet #
    existing_sam = Existing_Sam() # Users from SAM.csv #
    print(f'[DEBUG] Users already in SAM.csv: {[sam['SAM'] for sam in existing_sam]}')
    
    # <> Process each user that are in the Google Sheet <> #
    for user in users:
        # <> Get users login as SAM format (first last) <> #
        login = Get_SAM(user['Email Address'])

        # <> Try to fix Original OU Column <> #
        for sam in existing_sam:
            if sam.get('Original OU') == '' or 'No CA Restrictions' in sam.get('Original OU'):
                print(f'{sam['SAM']} missing OU')
                sam['Original OU'] = Fix_OUs(sam['SAM'])

        # <> Datetime Variables <> #
        date_format = '%m/%d/%Y'
        try:
            departure_date = datetime.strptime(user['Departure Date'], date_format)
            return_date = datetime.strptime(user['Return Date'], date_format)
            todays_date = datetime.today()
        except Exception as e:
            print(f'[ERROR] Unable to cast departure/return as datetime objects. Check data entered.')

        # <> Protect against misentered return/departure date <> #
        if departure_date == return_date:
            print(f'[ERROR] Cannot process {login}: departure_date and return_date are same value.')
            continue
        
        # <> User Returned to the US <> #
        try:
            if return_date <= todays_date:
                print(f'[DEBUG] Moving {login} back to their original OU')
                for sam in existing_sam:
                    if sam.get('SAM') == login:
                        sam['Remove'] = 'Yes'
                        delete_list.append(sam.get('SAM').replace(' ', '.').lower())
                continue
        except Exception as e:
            print(f'[ERROR] Unable to process {login}:\n {e}')

        # <> User still out of the US <> #
        if any(sam['SAM'] == login for sam in existing_sam):
            print(f'[DEBUG] {login} already in sam.csv. Moving to next user.')
            continue

        # <> Move user to NoCA and ReEnable account if needed <> #
        try:
            if departure_date <= todays_date:
                print(f'[DEBUG] Moving {login} to No CA OU.')
                sam_list.append({'SAM': login, 'Original OU': '', 'Remove': ''})
        except Exception as e:
            print(f'[ERROR] Unable to Process {login}:\n {e}')

    # <> combine the existing list and new list for writeback <> #
    final_list = existing_sam + sam_list

    # <> Write the updated list back to the SAM.csv <> #
    with open('PATH_TO_FILE', mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ['SAM', 'Original OU', 'Remove']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_list)

    # <> If there are users who have returned remove them from the Google Sheet <> # 
    if delete_list:
        Delete_From_GSheet(delete_list)
    
# <> Variables and FilePaths <> #
# - Build credential set - #
CREDENTIALS = 'PATH_TO_CREDENTIALS.json'
TOKEN = 'PATH_TO_TOKEN.json'
# - GOOGLE API SCOPES (Cloud Platform) - #
SCOPE = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]
# - Spreadsheet Info - #
SAM_Sheet = "PATH_TO_CSV_OF SAMs"
spreadsheet_id = 'GOOGLE_SHEET_ID_FOUND_IN_URL'
sheet_id = 'INDIVIDUAL_SHEET_ID'
# - Powershell Script  - #
script_path = "PATH_TO_POWERSHELL"

# <> Function Calls <> #
if __name__ == '__main__':
    service = build('sheets', 'v4', credentials = Authenticate())
    Move_Users(service, SAM_Sheet)
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path])
    print(f'Finished running at {datetime.now()}')