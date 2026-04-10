# <> Config file for variable storage <> #
import os
# - File Paths - #
key = os.environ.get('NoCA_Key')
if not key:
    raise RuntimeError('Unable to retrieve NoCA_Key')
ps1_path = 'noCaTrigger.ps1'
log_file = 'poller_logs.log'

# - API Variables - #
scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
file_id = 'id'
range = 'Trigger!A2'

# - Email Variables - #
server = 'smtp-relay.gmail.com'
port = 587
from_address = 'SENDER'
to_address = 'RECIPIENT'
body = 'run_check returned None. Check NoCAPoller on GCDS for errors.'
subject = 'NoCAPoller Error Alert'
