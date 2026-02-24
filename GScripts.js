//These are the various functions I have running in the Google App Script Extension on our travel form

//SCRIPT 1 autoFormUpdate.gs
//Every time a new form submission is done, it will automatically trigger the script to run
//by changing the version cell
function onFormSubmit(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const control = ss.getSheetByName('Trigger');
  if (!control) return;
  // Write a new UTC timestamp string into B2
  const timestamp = new Date().toISOString();
  control.getRange('B2').setValue(timestamp)
  control.getRange('A2').setValue('RUN');
}

//SCRIPT 2 returnDateCheck.gs
//Checks dates daily for any active returns or departure and changes the cells
function onReturn(main_sheet, target_cell, today, tz){
  //Get all dates in the return column
  const return_dates = main_sheet.getRange('D2:D').getValues();

  //Stop the function if value already says run or processing - prevent over running
  const target_value = target_cell.getValue()
  if (target_value.toLowerCase == 'run' || target_value.toLowerCase == 'processing'){
    return;
  }

  //Iterate through list of return dates
  for (let i = 0; i < return_dates.length; i++){
    const cell = return_dates[i][0];
    //Skip if Blank
    if (!cell) continue;

    //Format cell value to be a date object in the mm/dd/yyyy format
    const cell_formatted = Utilities.formatDate(cell, tz, 'MM/dd/yyyy');
    console.log(cell_formatted);

    //Run the script if departure date is equal to today
    if (cell_formatted <= today){
      console.log(cell_formatted);
      target_cell.setValue('RUN');
      return;
    }
  }
  
}

function departureCheck(main_sheet, target_cell, today, tz){
  //Get all dates in the departure column
  const departure_dates = main_sheet.getRange('C2:C').getValues();

  //Stop the check if run is already in the cell - prevent over running
  const target_value = target_cell.getValue();
  if (target_value.toLowerCase() == 'run' || target_value.toLowerCase() == 'processing'){
    return;
  }
  //Iterate through list of departure dates
  for (let i = 0; i < departure_dates.length; i++){
    const cell = departure_dates[i][0];

    //Skip if Blank
    if (!cell) continue;

    //Format cell value to be a date object in the mm/dd/yyyy format
    const cell_formatted = Utilities.formatDate(cell, tz, 'MM/dd/yyyy');
    console.log(cell_formatted)

    //Has this user already been taken care of?
    j = 1
    j = j + i

    //Run the script if departure date is equal to today
    if (cell_formatted <= today){
        target_cell.setValue('RUN')
        console.log('Setting target_cell to "Run"!')
        return;
    }
  }
}

function mainCall(){
  //identify constants
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const main_sheet = ss.getSheetByName('Form Responses 1');
  const target_sheet = ss.getSheetByName('Trigger')
  const target_cell = target_sheet.getRange('A2')

  //Generate a date object with todays date in mm/dd/yyyy format
  const tz = 'America/Los_Angeles';
  const today = Utilities.formatDate(new Date(), tz, 'MM/dd/yyyy');
  console.log(today);

  onReturn(main_sheet, target_cell, today, tz);
  departureCheck(main_sheet, target_cell, today, tz);

}

//Script 3 emailValidator.gs
//Checks for any invalid emails from the form submission. I tried to box it in using 
//regex confirm it follows the format of our emails but user errors still occur
function sendEmail(invalidArr){
  invalidArr.unshift('<h3>Invalid Emails detected in sheet. Fix as soon as possible.</h3>')
  
  const body = invalidArr.join('')
  console.log(body)
  MailApp.sendEmail({
    to: 'nate.quantock@mercerislandschools.org',
    subject: 'Invalid Emails Entered for NoCA',
    htmlBody: body,
    cc: 'network.admins@mercerislandschools.org'
  });
}

function validateEmails() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const main_sheet = ss.getSheetByName("Form Responses 1");
  const emailColumns = main_sheet.getRange('G:J')
  const backgrounds = emailColumns.getBackgrounds()

  const invalidColor = '#e06666'
  const validColor = '#b7e1cd'
  const whiteSpace = '#ffffff'

  const startRow = 1
  const startCol = 7

  invalidArr = ['<ul>Invalid Emails Entered in:']

  backgrounds.forEach((rowArr, rowIndex) =>{
    rowArr.forEach((color, colIndex) =>{
      const row = startRow + rowIndex
      const col = startCol + colIndex

      if (color !== whiteSpace && color !== validColor){
        const cell = main_sheet.getRange(row,col).getA1Notation()
        const value = main_sheet.getRange(cell).getValue()
        console.log(value)
        //console.log(`Cell ${cell} has color ${color}`)
        invalidArr.push(`<li>Cell: <strong> ${cell} </strong> >> Value Entered: <strong>${value}</strong></li>`)
      }
    })
  })
  console.log(invalidArr)
  if (invalidArr.length > 1){
    sendEmail(invalidArr)
  }
  else{
    console.log('Nothing to report...')
  }
}


//Script 4 incorrectEmail.gs
//Automatically send an email if someone submitted a form as staff or student but the recorded email was
//not one in our domain
function sendMail(value, key){
  console.log(key)
  console.log(value)
  email_body = `<p>Hello,<br><br>
    You are receiving this email because you submitted an Out of Country Travel Form Response. In this response, 
    you indicated that you were a "Student or Staff Member", but your email address recorded did not end in <strong>@studentdomain.org</strong> 
    or<strong>@staffdomain.org </strong>. Please resubmit the form at the link below with the corrected information; otherwise, 
    your submission cannot be properly processed. If you have any questions, please reply to this email.<br><br>

    <strong> Email you entered: </strong> ${value}<br><br>


    <strong> Link to Form: </strong> <a href="FORM_LINK">Out of Country Travel Form</a>
    <br><br>
    Regards,</p><br>

    Network Administrators<br>
    Phone: admin phone number<br>
    Email: admin email<br>
    Tickets: ticket email<br>
    `
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty(key)){ return 
  }else{
    MailApp.sendEmail({
      to: 'nate.quantock@mercerislandschools.org',
      //to: value,
      subject: 'Invalid Emails Entered for NoCA',
      htmlBody: email_body,
      //replyTo: 'network.admins@mercerislandschools.org'
    });
    props.setProperty(key, value)
    console.log(`Added ${key}:${value} to the sent list`)
  }
}

function mailCheck() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const main_sheet = ss.getSheetByName("Form Responses 1");
  const email_column = main_sheet.getRange("B:B")
  const backgrounds = email_column.getBackgrounds()



  startRow = 1
  startCol = 2

  invalidColor = "#cc0000"

  //Iterate through all cells
  backgrounds.forEach((rowArr, rowIndex) =>{
    //Iterate through each row
    rowArr.forEach((color, colIndex) =>{
      // Get row and column value based on start + current
      const row = startRow + rowIndex
      const col = startCol + colIndex

      //If invalid email for the selection
      if (color == invalidColor){
        //Get the cell reference and value
        const cell = main_sheet.getRange(row,col).getA1Notation()
        const value = main_sheet.getRange(cell).getValue()

        //Get the timestamp for storing a unique key that won't shift
        const time_cell = main_sheet.getRange(row, col-1).getA1Notation()
        const timestamp = main_sheet.getRange(time_cell).getValue()

        //Create the key:value pair
        const key = `sent:${timestamp}`

        //Send the email
        sendMail(value, key)
      }
    })
  })

}

