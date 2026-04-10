# <> Config.py for environment variables <> #
import config
# <> Built in modules <> #
import subprocess
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
# <> Third Party Modules <> #
import smtplib
import google.oauth2.service_account
from apiclient import discovery
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText

logger = logging.getLogger('NoCAPoller log')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
handler = TimedRotatingFileHandler(config.log_file, when='D', interval=15, backupCount=2)
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
            config.key, scopes=config.scopes)
            return discovery.build('sheets', 'v4', credentials=credential)
        except Exception as e:
            logger.critical(f'Could not generate service credentials: {e}')
            raise

    # <> Get the actual cell values of the spreadsheet <> # 
    def get_cell(self):
        try:
            results = (
                self.service.spreadsheets().values().get(
                    spreadsheetId=config.file_id, range=config.range
                    ).execute()
            )
            value = results.get('values')
            logger.info(f'Got value: {value}')
            return value[0][0]
        except HttpError as e:
            logger.critical(f'[ERROR] Could not get control cell: {e} \nTerminating program.')
            raise

# <> Function to send a quick email in case of any errors that might occur when trying to read the cell <> #
def email_alert():
    email = MIMEText(config.body, 'plain')
    email['Subject'] = config.subject
    email['From'] = config.from_address
    email['To'] = config.to_address
    try:
        with smtplib.SMTP(config.server, config.port) as server:
            server.starttls()
            server.sendmail(config.from_address, config.to_address, email.as_string())
            logger.info('Sent Email to network.admins to review errors')
    except Exception as e:
        logger.error(f'Could not send email: {e}')

def process_trigger(trigger):
    if trigger:
        if trigger.lower().strip() == 'do not run':
            logger.warning('Exiting: "Do Not Run" flag set.')
            sys.exit()
        elif trigger.lower().strip() == 'processing':
            logger.warning('Exiting: NoCA currently running..')
            sys.exit()
        elif trigger.lower().strip() == 'run':
            try:
                result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", config.ps1_path],capture_output=True)
                logger.info(f'Executed ps1 to trigger NoCA on DC4:{result.stdout}')
            except Exception as e:
                logger.critical(f'Could not run ps1 to trigger NoCA: {e}')
                raise
        elif trigger.lower().strip() == 'dormant':
            logger.info(f'Nothing to process: run_check == {trigger}')
            sys.exit()
        else:
            logger.error('Cell does not contain any valid options. Check "Trigger" tab')
            email_alert()
            return
    else:
        logger.error('Run_Check returned None.. closing Script and sending alert')
        email_alert()
        return

if __name__ == '__main__':
    logger.info('Polling NoCA')
    # Instantiate Google Service #
    service = GoogleService()
    # Get value of target_cell #
    trigger_value = service.get_cell()
    # Process cell value #
    process_trigger(trigger_value)
    logger.info('Polling NoCA Completed')



