# callmon
A Linux CallMonitor for the FritzBox.

![screenshot](http://dede67.bplaced.net/PhythonScripte/callmon/clientCallOpen.png)

The Callmonitor has a client- and a server-part.
The server-part should run all the time (for example on a Raspberry Pi).
The client-part runs on Linux systems with a GUI and connects to the server-part.

* The Callmonitor requires a **Python interpreter** in version 2.7.x for both parts (client & server).
* Also for both parts **python-pycrypto** (or **python-crypto**) and **python-lxml** is needed.
* Only the client requires **wxWidgets** (or **wxPython**) in version 2.8.
* The server requires **sqlite3**, **python-requests** and **python-cssselect**.

All files should exist on both sides.
* The server-script is `CallMonServer.py`.
* The client-script is `CallMonClient.py`.
* There are three service-scripts for the server-side: `exportFinishedCallsFromDB.py`, `deleteFinishedCallsFromDB.py` and `printFinishedCalls.py`.

There is a variable `OWN_AREA_CODE` in the server-script, that has to be set to the own area code.
And the callmonitor on the FritzBox has to be turned on with the sequence `#96*5*` (on a phone connected to the FritzBox).

The full documentation (in german language) is available at my [homepage](http://dede67.bplaced.net/PhythonScripte/callmon/callmon.html).
