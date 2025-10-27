{\rtf1\ansi\ansicpg1252\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 Import-Module ActiveDirectory\
\
$csvPath = \'93PATH_TO_CSV\'94\
\
$users = Import-Csv $csvPath\
\
$updatedUsers = @()\
\
foreach ($user in $users)\{\
    $preSAM = $user.SAM\
    $SAM = $preSAM.trim()\
\
    try \{   \
        $adUser = Get-ADUser -LDAPFilter "(sAMAccountName=$SAM)" -Properties DistinguishedName\
        $dn = $adUser.DistinguishedName\
        $originalOU = ($dn -split ",", 2)[1]\
        Enable-ADAccount -Identity $SAM\
\
        if($user.Remove -eq 'Yes')\{\
            $destinationOU = $user.'Original OU'\
            Write-Host "Setting $SAM to be removed from NoCA"\
            try\{\
                Move-ADObject -Identity $dn -TargetPath $destinationOU\
                Write-Host "Moved $SAM from $originalOU to $destinationOU" -ForegroundColor Green\
                $user.Remove = ''\
\
                \}\
            catch\{\
                Write-Host "Failed to move $SAM from $originalOU to $destinationOU" -ForegroundColor Red\
\
            \}\
            continue\
        \}\
        elseif($originalOU -like '*No CA*' -and $user.Remove -eq '')\{\
            write-host "Skipping $($SAM): already in No CA"\
            $updatedUsers += $user\
            continue\
        \}\
\
        $user.'Original OU' = $originalOU\
\
        if ($originalOU -like "*OU=Staff*") \{\
            $destinationOU = \'91STAFF OU\'94\
            Write-Host "original OU=Staff so destinationOU is: $destinationOU"\
        \}\
        elseif ($originalOU -like "*OU=STUDENT OU*\'94)\{\
            $destinationOU = \'91STUDENT OU\'94\
            Write-Host "original OU= STUDENT OU so destinationOU is: $destinationOU"\
	#Repeat as necessary for all of the OUs you are working with\
        else\{\
            $destinationOU = $originalOU\
            Write-Host "[Error] User was not found in a staff or student OU"\
        \}\
        Move-ADObject -Identity $dn -TargetPath $destinationOU\
\
\
        Write-Host "Moved $SAM from $originalOU to $destinationOU" -ForegroundColor Green\
\
    \}\
    catch \{\
        Write-Host "Failed to process SAM: $_" -ForegroundColor Red\
        $user.'Original OU' = $originalOU\
    \}\
    \
    $updatedUsers += $user\
\}\
\
$updatedUsers | Export-Csv -Path $csvPath -NoTypeInformation\
\
}