# <> Config.py for environment variables <> #
import config
from config import log
# <> Built in modules <> #
import os
import subprocess
import sys
from datetime import datetime
# <> Third Party Modules <> #
import smtplib
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText

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

# <> Get the actual cell values of the spreadsheet <> # 
def Get_Value_List(sheets, file_id):
    try:
        results = (
            sheets.spreadsheets().values().get(spreadsheetId=file_id, range=config.range).execute()
        )
        value = results.get('values')
        log.info(f'Got value: {value}')
        return value[0][0]
    except HttpError as e:
        log.error(f'[ERROR] Could not get control cell: {e}')
        return None

# <> Function to send a quick email in case of any errors that might occur when trying to read the cell <> #
def Email_Alert():
    email = MIMEText(config.body, 'plain')
    email['Subject'] = config.subject
    email['From'] = config.from_address
    email['To'] = config.to_address
    try:
        with smtplib.SMTP(config.server, config.port) as server:
            server.starttls()
            server.sendmail(config.from_address, config.to_address, email.as_string())
            log.info('Sent Email to network.admins to review errors')
    except Exception as e:
        log.error(f'Could not send email: {e}')

# <> Build credential set <> #
CREDENTIALS = config.cred_path
TOKEN = config.token_path
# - Any time you change the Scopes here, delete the token.json and re run the script to generate a new one with the correct Scopes included - #
SCOPE = config.scopes
file_id = config.sheet_id
invoke_ps1 = config.ps1_path

if __name__ == '__main__':
    # <> Logging <> #
    timestamp = datetime.now().strftime('%H:%M')
    log.info(f'Polling Google Sheet at {timestamp}')
    
    # <> Credential sets <> #
    creds = Authenticate()
    sheets = build('sheets', 'v4', credentials=creds)

    # <> Call Functions <> #
    # - Confirm Run_Check returned the value, and if it says 'Run' invoke No_CA on the domain controller - #
    run_check = Get_Value_List(sheets, file_id)
    if run_check:
        if run_check.lower().strip() == 'do not run':
            log.warning('Exiting: "Do Not Run" flag set.')
            sys.exit('Exiting: "Do Not Run" flag set.')
        elif run_check.lower().strip() == 'processing':
            log.warning('Exiting: NoCA currently running..')
            sys.exit('Exiting: NoCA currently running..')
        elif run_check.lower().strip() == 'run':
            try:
                subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", invoke_ps1])
                log.warning('Running PS1 to trigger NoCA')
            except Exception as e:
                log.error(f'Could not run powershell script: {e}')
        elif run_check.lower().strip() == 'dormant':
            log.info(f'Nothing to process: run_check == {run_check}')
        else:
            log.error('Cell does not contain any valid options. Please check Trigger tab')
    else:
        log.error('Run_Check returned None.. closing Script and sending alert')
        Email_Alert()


