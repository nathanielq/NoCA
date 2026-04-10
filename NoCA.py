# <> Config file <> #
import config
# <> Import built in modules <> #
import csv
import time
import logging
import subprocess
from logging.handlers import TimedRotatingFileHandler

# <> Import 3rd Party Modules <> #
import pandas as pd # used for individual cell manipulation
import polars as pl # used for speed for quick filter and rewrite
import google.oauth2.service_account
from datetime import datetime, timedelta
from apiclient import discovery
from googleapiclient.errors import HttpError

# Create the logger object #
logger = logging.getLogger('NoCA Log')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
handler = TimedRotatingFileHandler(config.log_path, when='D', interval=30, backupCount=12)
handler.setFormatter(formatter)
logger.addHandler(handler)


# <> Class for generating service account creds and taking actions on its behalf <> #
class GoogleService:
    def __init__(self):
        self.service = self.get_service()

    # <> Updated oauth2 method of creating service account credentials <> #
    def get_service(self):
        try:
            credential = google.oauth2.service_account.Credentials.from_service_account_file(
            config.key, scopes=config.scope)
            return discovery.build('sheets', 'v4', credentials=credential)
        except Exception as e:
            logger.critical(f'Could not generate service credentials: {e}')
            raise
         
    # <> Update the control cell to be dormant again. Prevent poller from re-triggering NoCA <> #
    def set_version_cell(self, state):
        values = [[state]] # sheets API requires 2D array to write to a cell
        body={'values':values}
        value_input_option = config.input
        try:
            result = self.service.spreadsheets().values().update(
                spreadsheetId=config.spreadsheet_id,range=config.range,
                valueInputOption=value_input_option,body=body
                ).execute()
            logger.info(f'{result.get('updatedCells')} cells updated')
        except HttpError as e:
            logger.error(f'Could not write to cell: {e}')

    # <> Read in users from NoCA csv. Contains their full name, start-date, end-date, and Parent OU (either staff, or building if it is a student) <> #
    def get_users(self):
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=config.spreadsheet_id,
                range=config.cell_range
                ).execute()
            logger.info('Retrieved users from Google Sheet')
        except Exception as e:
            logger.critical(f'Error retrieving users: {e}.\n Terminating program...')
            raise
        # - Reminder: this pulls from the 'Working Sheet' tab not Form Responses - #
        values = result.get('values', [])
        headers = values[0]
        users = [dict(zip(headers,row)) for row in values[1:]] #FIXME Itertools
        return users
    
    # <> Once a user has been set to move back from NoCA this function runs to delete their form record from the Google sheet to keep it cleaner and reduce bugs <> #
    def delete_from_gsheet(self, rows_to_delete):
        requests = []
        for row in reversed(rows_to_delete):
            logger.info(f'Index to delete: {row}')
            requests.append({
                "deleteDimension": {
                    "range": {
                        "sheetId": config.sheet_id, 
                        "dimension": "ROWS",
                        "startIndex": row,
                        "endIndex": row + 1
                    }
                }            
            })
        try:
            self.service.spreadsheets().batchUpdate(spreadsheetId=config.spreadsheet_id,
                                        body={"requests": requests}
                                        ).execute()
            logger.info(f"Succesfully deleted users") 
        except Exception as e:
            logger.error(f'{e}')


# <> Class for processing current and upcoming travelers <> #
class TravelerProcessor:
    def __init__(self):
        self.delete_list = []
        self.current_travelers = self.get_travelers()
    
    # <> Correct OUs if saved incorrectly <> #
    def get_travelers(self):
        try:
            with open(config.travelers_sheet, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                current_travelers = {row['SAM'].lower(): row for row in reader}
        except Exception as e:
            logger.critical(f"Could not open existing SAM file: {e} terminating program...")
            raise
        try:
            df = pd.read_csv(config.OU_csv, encoding='utf-8')
        except Exception as e:
            logger.error(f'Could not read OUs sheet and therefore cannot correct any OUs: {e}')
            return current_travelers
        return self.fix_ous(current_travelers, df)

    # <> Attempt to fix any user with a missing original OU <> #
    def fix_ous(self, current_travelers, df):
        ou_map = dict(zip(df['Name'].str.lower(), df['OU']))
        for traveler in current_travelers.values():
            if traveler.get('Original OU') == '' or 'No CA Restrictions' in traveler.get('Original OU'):
                logger.info(f'{traveler['SAM']} missing OU')
                original_ou = ou_map.get(traveler['SAM'].lower(), '')
                if original_ou:
                    traveler['Original OU'] = original_ou
                else:
                    logger.warning(f"No OU found for {traveler['SAM']}. Nothing updated.")
        return current_travelers
    
    # <> Process dates recorded against current date to make moves <> #
    def date_checks(self, user, sam_name):
        # Get dates as datetime objects #
        try:
            departure_date = datetime.strptime(user['Departure Date'], config.date_format)
            return_date = datetime.strptime(user['Return Date'], config.date_format)
        except Exception as e:
            logger.error(f'Could not parse dates for {sam_name}:\n {e}')
            return
        return_date += timedelta(days=1) #offset since users might access while traveling home
        todays_date = datetime.today()

        # Protect against misentered return/departure date #
        if departure_date == return_date:
            logger.error(f'[ERROR] Cannot process {sam_name}: departure_date and return_date are same value.')
            return
        # User Returned to the US #
        elif return_date <= todays_date:
            logger.info(f'Moving {sam_name} back to their original OU')
            if sam_name.lower() in self.current_travelers:
                self.current_travelers[sam_name.lower()]['Remove'] = 'Yes'
            self.delete_list.append(sam_name.replace(' ', '.').lower().strip())
            return
        # User still out of the US #
        elif sam_name.lower() in self.current_travelers:
            logger.info(f'{sam_name} already in sam.csv. Moving to next user.')
            return
        # Move user to NoCA and ReEnable account if needed #
        elif departure_date <= todays_date:
            logger.info(f'Moving {sam_name} to No CA OU.')
            self.current_travelers[sam_name.lower()] = {'SAM': sam_name, 'Original OU': '', 'Remove': ''}
        

# <> Delete any users marked as 'Yes' <>
def delete_from_csv():
    final_df = pl.read_csv(config.travelers_sheet, encoding='utf8')
    final_df = final_df.filter(pl.col('Remove') != 'Yes')
    final_df.write_csv(config.travelers_sheet)

# <> Build a list of rows to be deleted <> #
def build_delete_list(users, delete_list):
    # - create a set to compare values already seen so duplicates don't occur - #
    rows_to_delete = []
    delete_set = set(delete_list)

    for i, row in enumerate(users, start=1):
        if row['UserType'] == 'Student or Staff Member' and row['Email Address'].split('@')[0].strip().lower() in delete_set:
            rows_to_delete.append(i)
        elif row['UserType'] == 'Parent/Guardian' and row['Email_1'].split('@')[0].strip().lower() in delete_set:
                rows_to_delete.append(i)

    # - Use the method within sheets_service class previously instantited to delete the rows
    sheets_service.delete_from_gsheet(rows_to_delete)

# <> Get the users UPN by removing the email domain and the period <> #
def get_sam(email):
    # - split email address in to a list of its parts split at each period e.g. [first, last, @misd400.org] - #
    name = email.split('@')[0].split('.')
    # - How to process for students that have their middle initial in their email - #
    if email.count('.') == 3:
        username = name[0] + ' ' + name[1] + ' ' + name[2]
    # - Normal email processing - #
    else:
        username = name[0] + ' ' + name[1]
    return username

# <> write back updated list of travelers and remove any returned users from google sheet <> #
def finalize(users):
    # Write the updated list back to the SAM.csv #
    try:
        with open(config.travelers_sheet, mode='w', newline='', encoding='utf-8') as file:
            fieldnames = ['SAM', 'Original OU', 'Remove']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(processor.current_travelers.values())
    except Exception as e:
        logger.critical(f"Could not write rows to travelers_sheet {e}")
        raise
    
    # If there are users who have returned remove them from the Google Sheet # 
    if processor.delete_list:
        logger.info(f"Deleting {len(processor.delete_list)} row(s) from Google Sheet")
        for delete in processor.delete_list:
            logger.info(f'User to delete {delete}')
        build_delete_list(users, processor.delete_list)

#  New process main branch  #
def process_users():
    users = sheets_service.get_users()
    #  Process each user that are in the Google Sheet  #
    for user in users:
        #  Get users login as SAM format (first last)  #
        if user['UserType'] == 'Student or Staff Member':
            if user['Email Address'].split('@')[1] not in config.domains:
                logger.warning(f'Skipping {user['Email Address']}: not an misd email')
                continue
            processor.date_checks(user, get_sam(user['Email Address']))
        elif user['UserType'] == 'Parent/Guardian':
            num_students = int(user['Num_Students']) + 1
            for i in range(1, num_students):
                if not user.get(f'Email_{i}'):
                    continue
                processor.date_checks(user, get_sam(user.get(f'Email_{i}')))
    # Trigger final writing and deletion 
    finalize(users)

def run_powershell():
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", config.script_path],
            capture_output= True,
            text = True,
            check=False) 
        logger.info(result.stdout)
    except Exception as e:
        logger.error(f'Unable to run OU_Mover.ps1: {e}')
    time.sleep(3)
    
# <> Function Calls <> #
if __name__ == '__main__':
    # Start run # 
    logger.info('Starting NoCA.py')
    # - instantiate Classes - #
    sheets_service = GoogleService()
    processor = TravelerProcessor()

    # - set in process state - #
    sheets_service.set_version_cell('Processing')

    # - call functions - #
    process_users()
    run_powershell()
    delete_from_csv()

    # - set finished state - #
    sheets_service.set_version_cell('Dormant')

    #Finish Run
    logger.info('Finished running NoCA.py')
