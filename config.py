# <> Config file for variable storage <> #
# - Logger - #
from Logger_File import Logger
log = Logger(name='poller_log').Get_Logger()
# - File Paths - #
cred_path = 'PATH_TO_CREDS.json'
token_path = 'PATH_TO_TOKEN.json'
ps1_path = 'PATH_TO_PS1'

# - API Variables - #
scopes = [ "https://www.googleapis.com/auth/drive.metadata",
         "https://www.googleapis.com/auth/spreadsheets.readonly"]
sheet_id = 'GSheet_ID'
trigger_cell = 'SheetName!A2'

# - Email Variables - #
server = 'smtp-relay.gmail.com'
port = 587
from_address = 'SENDER'
to_address = 'RECIPIENT'
body = 'run_check returned None. Check NoCAPoller for errors.'
subject = 'NoCAPoller Error Alert'