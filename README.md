# VEVOR-diesel-air-heater-for-Windows
newer/common AirHeater-style transport on windows

Install:

Replace:

    WRITE_UUID = " "
    NOTIFY_UUID = " "
 
    
    py -m pip install bleak rich

Run it:       

 cd C:\Users\XXXXX\VEVOR-diesel-air-heater-for-Windows                              

    py heater5199_windows.py "Heater5199" 

Then test these:                 

    status

    up

    up

    down

    on

    vent

    off


The Temp is the Only part decoded at the moment. 
