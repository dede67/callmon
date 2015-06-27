#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
from Queue import Queue
import time
import lxml.html

from CallMonitorMessage import CallMonitorMessage
from Database import Database

# 23.04.2015  Änderung bei der 11880-Suche von h3 auf h1 in root.cssselect()

# ###########################################################
# 
class MessageToDatabase():
  def __init__(self, use_11880_queries, queue, own_area_code=""):
    self.own_area_code=own_area_code
    self.db=Database(self.own_area_code)
    self.update11880_queue=Queue()
    self.use_11880_queries=use_11880_queries
    self.fb_queue=queue

    if self.use_11880_queries==True:
      worker3=threading.Thread(target=self.runUpdate11880Name, name="runUpdate11880Name")
      worker3.setDaemon(True)
      worker3.start()

  # ###########################################################
  # Schreibt einen Meldungsstring von der Fritzbox nach
  # Aufbereitung in die Tabelle Log. Ausserdem wird zur
  # externen Nummer bei 11880 nach dem zugehörigen Namen
  # gesucht (sofern dieser nicht im Telefonbuch der Fritzbox
  # steht).
  def addMessage(self, msgstr):
    msg=self.__parseMessage(msgstr)               # Meldung von Fritzbox parsen
    if msg!=None:                                 # wenn Meldung valide ist
      if self.use_11880_queries==True:            # und 11880-Queries gewünscht sind
        if msg.typ in ("CALL", "RING"):           # und Verbindungsaufbau-Phase läuft
          self.update11880_queue.put(msg.num_ext) # Suche "Name zur Nummer" bei 11880 beauftragen
      self.db.insertLog(msg)                      # Meldung in DB schreiben
    return

  # ###########################################################
  # Läuft als Thread.
  # Nummern von der Queue empfangen, gegen die Tabellen
  # "Names" und "Names11880" testen. Wenn nicht enthalten oder
  # abgelaufen, bei 11880 den Namen zur Nummer [neu] anfragen,
  # beides in "Names11880" einfügen bzw. aktualisieren und
  # Refresh via CallMon-Server an CallMon-Clients schicken.
  def runUpdate11880Name(self):
    db=Database(self.own_area_code)
    ln=("1", "2", "3", "4", "5", "6", "7", "8", "9")
    while True:
      number=self.update11880_queue.get()             # auf neue Nummer warten
      if self.own_area_code!="" and number[:1] in ln: # wenn Nummer ohne Vorwahl gekommen ist...
        number=self.own_area_code+number              # ...Vorwahl voranstellen
      if len(number)==0 or number[:1] in ln:          # nur valide externe Nummern gegen 11880 testen
        continue
      if db.getNameFromNumber(number)==number:        # wenn Nummer nicht im Fritzbox-Telefonbuch steht
        n, e=db.getName11880FromNumber(number)        # Name und Ablaufstatus aus 11880-Telefonbuch holen
        if n==None or e==True:                        # wenn Name nicht enthalten oder abgelaufen
          name=self.queryNameForNumber(number)        # Name zur Nummer [neu] bei 11880 anfragen
          if name!=None:                              # wenn kein Fehler auftrat
            db.insertOrUpdateNames11880(name, number) # in DB schreiben
            if name!="":                              # nur wenn ein Name zur Nummer gefunden wurde
              self.fb_queue.put("REFRESH")            # refresh zum CallMon-Server, zur Weitergabe an die CallMon-Clients 

  # ###########################################################
  # Liefert ggf. einen Namen zu der Nummer "number".
  # Oder "", wenn kein Name gefunden wurde.
  # Bei Fehler wird None geliefert.
  # http://stackoverflow.com/a/27068734/3588613
  def queryNameForNumber(self, number):
    parser=lxml.html.HTMLParser(encoding='utf-8')
    rc=""
    try:
      root=lxml.etree.parse("http://www.11880.com/rueckwaertssuche/%s"%(number), parser=parser).getroot()
      h3=root.cssselect(b'h1')
      if len(h3)==1 and h3[0].get("itemprop")=="name":
        rc=h3[0].text_content()
        if len(rc)>40:
          rc=rc[:40]
    except Exception, e:
      print "Error in queryNameForNumber:", e
      rc=None
    return(rc)

  # ###########################################################
  # Nimmt einen Meldungs-String vom Fritzbox Callmonitor
  # entgegen und liefert ihn als CallMonitorMessage zurück.
  #
  # Format (gem. http://www.wehavemorefun.de/fritzbox/Callmonitor)
  #
  # Callmonitor-Support aktivieren        #96*5*
  # Callmonitor-Support deaktivieren      #96*4*
  #
  # datum;CALL      ;ConnectionID;Nebenstelle;GenutzteNummer;AngerufeneNummer;
  # datum;RING      ;ConnectionID;Anrufer-Nr;Angerufene-Nummer;
  # datum;CONNECT   ;ConnectionID;Nebenstelle;Nummer;
  # datum;DISCONNECT;ConnectionID;dauerInSekunden;
  #
  # mit FRITZ!OS 06.20 auf einer 7390 z.B.:
  #
  # -0----------------1----------2-3---4-----------5-----------6----
  # 06.11.14 17:15:30;CALL      ;1;12 ;046xxxxxxxx;0173xxxxxxx;SIP0;
  # 06.11.14 17:15:51;CONNECT   ;1;12 ;0173xxxxxxx;
  # 06.11.14 17:22:45;DISCONNECT;1;412;
  #
  # -0----------------1----------2-3-------------4-------------5----
  # 07.11.14 08:37:07;RING      ;0;0036xxxxxxxxx;046xxxxxxxx  ;SIP1;
  # 07.11.14 08:37:10;CONNECT   ;0;0            ;0036xxxxxxxxx;
  # 07.11.14 08:42:18;DISCONNECT;0;308;
  #
  # -0----------------1----------2-3-------------4-------------5----
  # 07.11.14 08:37:07;RING      ;0;             ;046xxxxxxxx  ;SIP1;   --- Nummer unterdrückt
  # 07.11.14 08:37:18;DISCONNECT;0;0;
  def __parseMessage(self, msgstr):
    msg=None
    rs=msgstr.split(";")
    if len(rs)>3:
      msg=CallMonitorMessage()
      msg.tmstmp=self.__convertTimestamp(rs[0])
      msg.typ=rs[1]
      msg.conid=rs[2]
      if msg.typ=="CALL":
        msg.tel=rs[3]
        msg.tel_pb=self.__numIntToName(rs[3])
        msg.num_int=rs[4]
        msg.num_ext=self.__stripFollowingHash(rs[5])
        if len(rs)>=7:
          msg.sip=rs[6]
      elif msg.typ=="RING":
        msg.num_ext=rs[3]
        msg.num_int=rs[4]
        if len(rs)>=6:
          msg.sip=rs[5]
      elif msg.typ=="CONNECT":
        msg.tel=rs[3]
        msg.tel_pb=self.__numIntToName(rs[3])
        msg.num_ext=rs[4]
      elif msg.typ=="DISCONNECT":
        msg.dur=rs[3]
      else:
        msg=None
        print "Error: unknown type"
    return(msg)

  # ###########################################################
  # Wandelt einen Timestamp im Format "07.11.14 10:46:44" nach
  # "2014-11-07 10:46:44".
  def __convertTimestamp(self, ts):
    t=time.strptime(ts, "%d.%m.%y %H:%M:%S")
    return(time.strftime("%Y-%m-%d %H:%M:%S", t))

  # ###########################################################
  # Liefert "number" ohne #-Zeichen am Ende.
  def __stripFollowingHash(self, number):
    number=number.strip()
    if number[len(number)-1:]=="#":
      number=number[:len(number)-1]
    return(number)

  # ###########################################################
  # Umsetzer für Nebenstelle nach Name gemäß Telefonbuch.
  # Gemäß wehavemorefun mit Korrekturen für FRITZ!OS 06.20
  #
  #-------------------------------------
  #Alle (Rundruf)             **9
  #-------------------------------------0-1 FON1/2
  #Büro                       **1       0
  #Tobi                       **2       1
  #-------------------------------------
  #ISDN(S0)                   **51      4
  #  [...]
  #ISDN(S0)                   **58      4
  #-------------------------------------
  #Fax                                  5
  #-------------------------------------10-19 DECT
  #Wohnzimmer                 **610     10
  #Küche                      **611     11
  #Henrike                    **612     12
  #Larsi                      **613     13
  #-------------------------------------20-29 VoIP-Telefone
  #VoIPwz                     **620     20
  #SIP-T20P                   **621     21
  #-------------------------------------40-44 Anrufbeantworter
  #Anrufbeantworter 1         **600     40
  #Anrufbeantworter 1 (memo)  **605
  #-------------------------------------
  def __numIntToName(self, numInt):
    try:
      numInt=int(numInt)
    except:
      if numInt=="":
        return("")
      return("numInt not numeric")

    if 0<=numInt<=2:
      nrpb="**"+str(numInt+1)     # 0  -> "**1"
    elif 10<=numInt<=19:
      nrpb="**6"+str(numInt)      # 10 -> "**610"
    elif 20<=numInt<=29:
      nrpb="**62"+str(numInt-20)  # 20 -> "**620"
    elif 40<=numInt<=44:
      nrpb="**60"+str(numInt-40)  # 40 -> "**600"
    else:
      nrpb=str(numInt)
    return(nrpb)

