# <> Config file <> #
import config
from config import log
# <> Import built in modules <> #
import csv
import os
import subprocess
import sys
import time
# <> Import 3rd Party Modules <> #
import pandas as pd
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
        try:
            with open(TOKEN, 'w') as token: #write the newly generated creds to Token.json to speed up this process if call is done wihthin the expiration time
                token.write(creds.to_json())
        except FileNotFoundError as e:
            print(f'File not found: {e}')
        except PermissionError as e:
            print(f'Error opening file: {e}')
        except Exception as e:
            print(f'Error with file {e}')
    return creds

# <> Update the control cell to be dormant again. Prevent poller from re-triggering NoCA <> #
def Set_Version_Cell(service,state):
    values = [[state]]
    body={'values':values}
    value_input_option = config.input
    try:
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,range=config.range,
            valueInputOption=value_input_option,body=body
            ).execute()
        log.info(f'{result.get('updatedCells')} cells updated')
    except HttpError as e:
        log.error(f'Could not write to cell: {e}')

# <> Read in users from NoCA csv. Contains their full name, start-date, end-date, and Parent OU (either staff, or building if it is a student) <> #
def Get_Users(service):
    cell_range = config.cell_range #sheet name and it's range of cells available
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id,range=cell_range).execute() #google module function to grab the contents of the spreadsheet
    values = result.get('values', []) # <> parse the output into just the cell values
    headers = values[0] #first row ['email address', 'departure date', 'return date']
    users = [dict(zip(headers,row)) for row in values[1:]] #convert the list of rows (lists) to a list of dicts. zip combines the headers and rows and casts as a dict the for loop looks at all rows past 
    return users

# <> Get the users UPN by removing the email domain and the period <> #
def Get_SAM(email):
    # - split email address in to a list of its parts split at each period e.g. [first, last, @misd400.org] - #
    name = email.split('@')[0].split('.')
    # - How to process for students that have their middle initial in their email - #
    if email.count('.') == 3:
        username = name[0] + ' ' + name[1] + ' ' + name[2]
    # - Normal email processing - #
    else:
        username = name[0] + ' ' + name[1]
    return username

# <> Once a user has been set to move back from NoCA this function runs to delete their form record from the Google sheet to keep it cleaner and reduce bugs <> #
def Delete_From_GSheet(delete_list):
    cell_range = config.cell_range
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id,range=cell_range).execute() #grab all values again
    values = result.get('values', [])
    log.info(delete_list)
    # - create a set to compare values already seen so duplicates don't occur - #
    rows_to_delete = []
    delete_set = set(delete_list)
    try:
        # - Iterate through the sheet from the first row - #
        for i, row in enumerate(values[1:], start=2):
            # - Keeping this in it's good for debugging - #
            # print(row[1].split('@')[0].strip().lower(), len(row), i)

            # - Row lengths vary but if they are staff/student or done by us len SHOULD be under 6, so Email Address col (1/B) is where this will be found - #
            if len(row) < 6 and row[1].split('@')[0].strip().lower() in delete_set:
                log.info(f"appending row {i - 1}")
                rows_to_delete.append(i - 1)
            # - If a family filling out on behalf of students it will always be over 6, and sometimes ones we enter are as well. Email will be in 1/B or 6/G - #
            elif len(row) > 6:
                if row[6].split('@')[0].strip().lower() in delete_list or row[1].split('@')[0].strip().lower() in delete_set:
                    log.info(f'appending row {i - 1}')
                    rows_to_delete.append(i - 1)

        log.info(rows_to_delete)

        # <> Iterate through the rows and delete from bottom up to prevent issues with shifting indices <> #
        requests = []
        for row in reversed(rows_to_delete):
            log.info(f'Index to delete: {row}')
            if row is not None:
                requests.append({ #Create requests list
                    "deleteDimension": { #Google API command to delete content
                        "range": {
                            "sheetId": sheet_id, 
                            "dimension": "ROWS",
                            "startIndex": row,
                            "endIndex": row + 1
                        }
                    }            
                })
        # - Send the batchupdate command with the full requests list one time - #
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id,
                                           body={"requests": requests}
                                           ).execute()
        log.info(f"Succesfully deleted: {row}")           
    except Exception as e:
        log.error(f'[ERROR]: {e}')
        

# <> Find a user to delete in the SAM CSV if not in GSheet <> #
def Delete_From_CSV(delete_list, df):
    new_df = df[~df['SAM'].isin(delete_list)] # only keeps rows where 'SAM' value is not in delete_list
    log.info(new_df)
    new_df.to_csv(SAM_Sheet, index=False, encoding='utf-8')

# <> Pull all existing users from the SAM csv for comparisons <> #
def Existing_Sam():
    existing_sam = []
    try:
        with open(SAM_Sheet, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                existing_sam.append(row)
    except FileNotFoundError as e:
        log.error(f'File not found: {e}')
    except Exception as e:
        log.error(f'Error opening file: {e}')
    
    return existing_sam

# <> OU in sam.csv can sometimes not be written correctly. This will attempt to correct it <> #
def Fix_OUs(user):
    log.info(f'User in Fix Ous: {user}')
    ou = ''
    try:
        df = pd.read_csv(config.OU_csv, encoding='utf-8')
        ou = df.loc[df['Name'].str.lower() == user.lower(), 'OU'].item()
        log.info(f'{user} originally in {ou}')
        if 'No CA' in ou or ou == '':
            ou = 'OU not found'  
            log.error(f'Could not correct {user} Original OU')
    except Exception as e:
        log.error(f'Could not correct {user} Original OU: {e}')
    return ou

# <> Process the users for Active Directory <> #
def Move_Users(service, SAM_Sheet):
    sam_list = []
    delete_list = []
    # <> Get users <> #
    users = Get_Users(service) # Users from Google Sheet #
    existing_sam = Existing_Sam() # Users from SAM.csv #

    # <> Try to fix Original OU Column in SAM.csv <> #
    for sam in existing_sam:
        if sam.get('Original OU') == '' or 'No CA Restrictions' in sam.get('Original OU'):
            log.info(f'{sam['SAM']} missing OU')
            sam['Original OU'] = Fix_OUs(sam['SAM'])

    log.debug(f'[DEBUG] Users already in SAM.csv: {[sam['SAM'] for sam in existing_sam]}')
    
    # <> Process each user that are in the Google Sheet <> #
    for user in users:
        logins = []
        #print(user)
        # <> Get users login as SAM format (first last) <> #
        if user['UserType'] == 'Student or Staff Member':
            try:
                logins.append(Get_SAM(user['Email Address'])) #FIXME with new change it will not always be email_address
            except Exception as e:
                log.error(f"Verify Email Validity: {e}")
        elif user['UserType'] == 'Parent/Guardian':
            num_students = int(user['Num_Students']) + 1
            for i in range(1, num_students):
                print(f'i= {i}')
                try:
                    logins.append(Get_SAM(user.get(f'Email_{i}')))
                except Exception as e:
                    log.error(f"Verify Email Validity: {e}")

        # <> Since we now will have multiple logins, process multiple logins per user entry <> #
        for login in logins:
            # <> Datetime Variables <> #
            # - If datetime cannot be cast to the user, skip the login being processed - #
            date_format = '%m/%d/%Y'
            try:
                departure_date = datetime.strptime(user['Departure Date'], date_format)
                return_date = datetime.strptime(user['Return Date'], date_format)
                return_date = return_date + timedelta(days=1)
                todays_date = datetime.today()
            except Exception as e:
                log.error(f'Error converting collected date into datetime object. User: {login}')
                continue

            # <> Protect against misentered return/departure date <> #
            if departure_date == return_date:
                log.error(f'[ERROR] Cannot process {login}: departure_date and return_date are same value.')
                continue
            
            # <> User Returned to the US <> #
            # - Updates made here. Add period to the name so 'in' will work - #
            elif return_date <= todays_date:
                log.info(f'[DEBUG] Moving {login} back to their original OU')
                for sam in existing_sam:
                    if sam.get('SAM').lower() == login.lower():
                        sam['Remove'] = 'Yes'
                delete_list.append(login.replace(' ', '.').lower().strip())
                continue

            # <> User still out of the US <> #
            elif any(sam['SAM'] == login for sam in existing_sam):
                log.info(f'[DEBUG] {login} already in sam.csv. Moving to next user.')
                continue

            # <> Move user to NoCA and ReEnable account if needed <> #
            elif departure_date <= todays_date:
                log.info(f'[DEBUG] Moving {login} to No CA OU.')
                sam_list.append({'SAM': login, 'Original OU': '', 'Remove': ''})
    

    # <> combine the existing list and new list for writeback <> #
    final_list = existing_sam + sam_list

    # <> Write the updated list back to the SAM.csv <> #
    try:
        with open(SAM_Sheet, mode='w', newline='', encoding='utf-8') as file:
            fieldnames = ['SAM', 'Original OU', 'Remove']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(final_list)
    except PermissionError as e:
        log.warning(f"Close the damn sam.csv >:^( {e}")
        sys.exit()
    except FileNotFoundError as e:
        log.warning(f'File not found: {e}')
        sys.exit()
    except Exception as e:
        log.warning(f'Error opening file: {e}')
        sys.exit()

    # <> If there are users who have returned remove them from the Google Sheet <> # 
    if delete_list:
        log.info(f"Deleting {len(delete_list)} row(s) from Google Sheet")
        for delete in delete_list:
            print(f'User to delete {delete}')
        Delete_From_GSheet(delete_list)
    
# <> Variables and FilePaths <> #
# - Build credential set - #
CREDENTIALS = config.CREDENTIALS
TOKEN = config.TOKEN
SCOPE = config.SCOPE
# - Spreadsheet Info - #
SAM_Sheet = config.SAM_Sheet
spreadsheet_id = config.spreadsheet_id
sheet_id = config.sheet_id
# - Powershell Script  - #
script_path = config.script_path

# <> Function Calls <> #
if __name__ == '__main__':
    # <> Set the time <> #
    now = datetime.now()

    # <> Logging <> #
    timestamp = now.strftime('%m/%d/%Y %H:%M')
    log.info(f'\nStarting NoCA at {timestamp}')
    
    # <> Main Calls <> #
    service = build('sheets', 'v4', credentials = Authenticate())
    Set_Version_Cell(service, 'Processing')
    Move_Users(service, SAM_Sheet)

    # <> Run the PS1 and capture output. Log the output <> #
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path],
            capture_output= True,
            text = True,
            check=False) 

        if result.stdout:
            log.info(f"Output from PS1: {result.stdout.rstrip()}")
        if result.stderr:
            log.error(f'Error output from PS1: {result.stderr.rstrip()}')
    except Exception as e:
        log.warning(f'Unable to run OU_Mover.ps1: {e}')
    time.sleep(3)
    Set_Version_Cell(service, 'Dormant')

    # <> Powershell run <> #
    try:
        subprocess.run(config.gcds)
    except FileNotFoundError as e:
        log.warning(f'Sync not found: {e}')
    except PermissionError as e:
        log.warning(f'Could not run sync. Permissioned Denied: {e}') 
    except Exception as e:
        log.warning(f'Uncaught error running sync:\n {e}')   
    log.info(f'Finished running at {datetime.now()}')