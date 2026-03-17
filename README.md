# NoCA
Tech Stack: Python, PowerShell, Google Sheets API, Google Apps Script, Google Forms

This Python script uses the Google Sheets API to get information from a Google Form Response Sheet. With that information specific moves are made in ActiveDirectory using Powershell

A more in depth description of this use case is that we use Google's Context Aware Access to recgonize and block access to all Google Apps when outside of the country. When users travel outside of the country we want them to still be able to access their accounts. If a user has either confirmed ahead of time their travel intentions, or has contacted while out of the country we will update and move them to an OU that allows out-of-country access. 

This script allows us to provide a Google Form that users can fill out which in turns saves to a Google sheet that my team can edit. The script will read the Google Sheet and look at a users departure and return dates and then the logic of the script will determine which OU they should be in for going out of the country. Their original OU is saved so they can be returned to that OU when they return to the states. I also have a fallback CSV of users OUs to reference in case for some reason the powershell script used to get their OU fails, or for any reason their original OU was not saved. When the logic has determined which move should be made a powershell script is triggered that makes the OU move in Active Directory (Our setup is Active Directory syncing to Google).

This has been upgraded to include a lightweight poller script that looks at a single cell to see if it should trigger the main script to run. A series of GS scripts are used to check departure and return dates of users, whether the form was submitted, and if there are issues with email addresses that have been submitted. These will change the cell that nocapoller looks at for its running.
