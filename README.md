# NoCA
Tech Stack: Python, Pandas, Polars, TimedRotatingFileHandler, PowerShell, Google Sheets API, Google Apps Script, Google Forms

This Python script uses the Google Sheets API to get information from a Google Form Response Sheet. With that information specific moves are made in ActiveDirectory using Powershell.

I have another program called GAM Detector that automatically disables user logins from outside of the country. When users travel Legitimately outside of the country we want them to still be able to access their accounts. If a user has either confirmed ahead of time their travel intentions, or has contacted while out of the country we will update and move them to an OU that allows out-of-country access and will not be disabled by the script. 

Users fill out a Google Form or notify us (network admins) of travel outside of the US, MX, or CA. Google Apps Script will validate the data in the responses Google Sheet and even send an email to the user if filled out incorrectly. Scripts in Apps Script will monitor departure and return dates. If it is determined that a move needs to be made for a user, a trigger cell is changed which a lightweight Python poller script reads via Sheets API. If it triggers a run, the poller will switch the cell to 'In progress' and trigger the main script to run. This script will process the user account and move the user in Active Directory via powershell script to different OUs as needed. It then returns the cell value back to 'dormant' and will modify the Google sheet to reflect the change. 



