#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import select
import threading
import time
import sys
from Queue import Queue
import json

# Folgende Paktete werden benötigt:
#   sqlite3
#   python-lxml
#   python-requests
#   python-pycrypto (bzw: python-crypto)

from MessageToDatabase  import MessageToDatabase    # import: CallMonitorMessage.py, Database.py
from Database           import Database             # import: CallMonitorMessage.py, MsgTyp.py
from GetPhonebook       import Phonebook
from ParseXML_Phonebook import ParseXML_Phonebook
from MiniCryptoV2       import MiniCryptoV2

OWN_AREA_CODE         ="04631"      # eigene Vorwahlnummer (wird Nummern aus dem Telefonbuch ohne führende Null vorangestellt)
FRITZBOX_IP           ="fritz.box"  # IP-Adresse oder Hostname der Fritzbox
CALLMON_SERVER_SOCKET =26260        # Port, auf dem CallMonServer.py lauscht
FRITZBOX_CALLMON_PORT =1012         # CallMonitor-Port auf der Fritzbox
USE_11880_QUERIES     =True         # auf True, um 11880.com bzgl. Name zu Nummer zu befragen. Sonst auf False
STATUS_TO_TERMINAL    =True         # auf True, um Status-Meldungen auszugeben

# start z.B. mit: screen -S callmon -d -m ~/callmon/CallMonServer.py

# ###########################################################
# 16.11.2014  1.0   erste Version
# 20.11.2014  1.0.1 Anpassungen im Format der Meldungsausgabe (via print)
#                   zugefügt: __updateClientAlias() und __getAllConnectedClientAliasNumbers()
# 21.11.2014  1.0.2 update von Telefonbuch-Einträgen zugefügt, damit die Nummern nicht immer gelöscht und wieder eingefügt
#                   werden - und dadurch die IDs in der Numbers-Tabelle ständig größer werden.
# 22.11.2014  1.1   Abfrage der Namen zu externen Nummern bei www.11880.com zugefügt
# 23.11.2014  1.1.1 "REFRESH" eingebaut
# 25.11.2014  1.1.2 bei der Kopie des Fritzbox-Telefonbuchs werden Nummern mit vorausgehender eigener Vorwahl nochmal
#                   ohne Vorwahl abgelegt bzw. dem Namen zugewiesen.
# 26.11.2014  1.1.3 Umstellung auf MiniCryptoV2 (jetzt mit private/public-Keys).
# 27.11.2014  1.1.4 "GET_CALLS_FOR" eingebaut, db.updateLogFinished() wird bei DISCONNECT jetzt direkt bzw. ohne COMMIT
#                   zwischendurch von db.insertLog() aufgerufen (damit in db.getRowsFromLog() kein DISCONNECT mehr vorkommen
#                   kann)
# 07.12.2014  1.1.5 Umstellung für PopupControl (Namen beim NOTIFY mitliefern)
# 12.12.2014  1.1.6 bei der 11880-Suche werden nun Nummern ohne Vorwahl um die Vorwahl ergänzt
# 24.12.2014  1.1.7 Berücksichtigung von OWN_AREA_CODE bei GET_CALLS_FOR
# 29.01.2014  1.1.8 Suchfunktion nach Nummer und Name eingebaut
# 25.02.2015  1.1.9 beim Kommando "GET_OWN_AREA_CODE" wird der Inhalt von "OWN_AREA_CODE" an den Client geliefert,
#                   STATUS_TO_TERMINAL eingebaut
# 26.04.2015  1.2   Anpassung von MessageToDatabase.queryNameForNumber() wegen Änderung bei 11880.com
# 13.05.2015  1.2a  try/except-Abfragen in Database.py um die INSERTs für Tabellen mit UNIQUE-Index (wegen mögl. Dupes
#                   im Fritzbox-Telefonbuch) und Warnings wegen fehlender Zertifikatsprüfung der Fritzbox in GetPhonebook.py
#                   abgeschaltet
#                   

VERSION="1.2a"

# ###########################################################
#
class CallMonServer():
  # - Ein Thread (worker1) empfängt von der Fritzbox die CallMonitor-Nachrichten und schreibt sie auf die Queue fb_queue.
  #
  # - Ein Thread (worker2) empfängt von der Queue fb_queue, schreibt in die DB, beauftragt ggf. über die Queue
  #   update11880_queue (bei worker3) die Suche bei 11880 nach einem Namen zur Nummer und sendet Notifications an alle
  #   verbundenen Clients.
  #
  # - Ein Thread (worker3 in MessageToDatabase()) empfängt von der Queue update11880_queue, sucht auf 11880 einen Namen
  #   zur Nummer und schreibt diesen ggf. in die Tabelle Names11880. Danach wird ein "REFRESH" auf fb_queue geschrieben.
  #
  # - Die Mainloop (runServer()) nimmt Verbindungen von Clients an und reagiert auf deren Kommandos.
  #   Auf jede Meldung wird geantwortet - mindestens mit "ERROR" oder "UNKNOWN_COMMAND".
  #
  # - Es gibt drei Instanzen der Datenbank-Klasse mit folgenden Zugriffsarten auf die Tabellen:
  #   - eine in runServer() als self.db
  #       lesend:       Log, LogFinished
  #       schreibend:   Names, Numbers
  #   - eine im Thread runMessageToDatabase() als self.m2db.db
  #       schreibend:   Log, LogFinished
  #       lesend:       Names, Numbers (via VIEW LogWithNames)
  #       lesend:       Names11880
  #   - eine im Thread runUpdate11880Name() in MessageToDatabase() als db
  #       lesend:       Names, Numbers
  #       schreibend:   Names11880
  #
  # - Eine Meldung von der Fritzbox nimmt folgenden Weg:
  #   - Empfang der Meldung im Thread runFritzboxCallMonitor()
  #   - Weitergabe via self.fb_queue an Thread runMessageToDatabase()
  #   - Empfang in runMessageToDatabase()
  #   - Weitergabe an self.m2db.addMessage
  #     - addMessage zerlegt die Meldung nach msg
  #     - addMessage beauftragt die Suche des Namens zur Nummer bei 11880 (sofern Nummer nicht
  #       im Fritzbox-Telefonbuch steht) über self.update11880_queue an Thread runUpdate11880Name()
  #     - addMessage schreibt msg über db.insertLog() in die Datenbank
  #       - db.insertLog() schreibt Satz in die Tabelle Log (noch ohne Namen zur Nummer)
  #       - erkennt db.insertLog() den Satz als DISCONNECT-Meldung, werden alle zur Meldung gehörenden
  #         Sätze in db.updateLogFinished() nach LogFinished kopiert und die Sätze in Log als bearbeitet
  #         gekennzeichnet (bzw. gelöscht). Dabei wird ggf. ein Name zur Nummer zugefügt. Entweder per
  #         JOIN aus dem Fritzbox-Telefonbuch, ansonsten in db.__fillCallMonitorMessage() aus der
  #         11880-Tabelle.
  #   - Rückkehr aus addMessage nach runMessageToDatabase()
  #   - NOTIFY an alle verbundenen Clients, dass sie ihre Daten aktualisieren sollen
  # - Clients warten auf NOTIFY vom Server und fragen je nach Meldungstyp folgendermaßen an:
  #   - bei einer RING, CALL oder CONNECT-Meldung wird per GET_OPEN_CALLS angefragt
  #     - der GET_OPEN_CALLS führt zu db.getRowsFromLog(), wo der VIEW LogWithNames abgefragt
  #       wird, zusammengehörige Sätze ggf. zu einem Satz zusammengeführt werden und ggf. in
  #       db.__fillCallMonitorMessage() um einen 11880-Namen erweitert werden.
  #   - bei einer DISCONNECT-Meldung wird erst GET_FINISHED_CALLS und dann GET_OPEN_CALLS angefragt
  #     - der GET_FINISHED_CALLS führt zu db.getRowsFromLogFinished(), wo einfach nur der Inhalt der
  #       Tabelle LogFinished geliefert wird
  #     - bzgl. GET_OPEN_CALLS: siehe voriger Punkt
  def __init__(self, port):
    self.port=port

    self.db=Database(OWN_AREA_CODE)
    delcnt=self.db.clearLogOnStartup() # Log-Tabelle von möglichen Resten säubern
    if delcnt>0:
      print "Anzahl bereinigter Sätze in der Log-Tabelle: %d"%delcnt
    self.crypto=MiniCryptoV2(1024)

    self.fb_queue=Queue() # Meldungs-Übergabe von runFritzboxCallMonitor() an runMessageToDatabase()
    self.clients={}       # hier wird die Socket-Paarigkeit gespeichert {clientname:(SteuerSocket, MeldungsSocket)}
    self.clientalias={}   # hier wird pro clientname eine Nummer vergeben (es wird nicht gelöscht)

    self.startFritzboxCallMonitor()

  # ###########################################################
  # Empfangs-Thread und Verarbeitungs-Thread aufsetzen.
  # Funktion verändert:
  #   startet zwei Threads
  def startFritzboxCallMonitor(self):
    worker1=threading.Thread(target=self.runFritzboxCallMonitor, name="runFritzboxCallMonitor")
    worker1.setDaemon(True)
    worker1.start()

    worker2=threading.Thread(target=self.runMessageToDatabase, name="runMessageToDatabase")
    worker2.setDaemon(True)
    worker2.start()

  # ###########################################################
  # Läuft als Thread.
  # Verbindung zur Fritzbox herstellen, Meldungen von der
  # Fritzbox empfangen und an Queue übergeben.
  # Funktion verändert:
  #   self.recSock
  #   self.fb_queue
  def runFritzboxCallMonitor(self):
    while True: # Socket-Connect-Loop
      self.recSock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      try:
        self.recSock.connect((FRITZBOX_IP, FRITZBOX_CALLMON_PORT))
      except socket.herror, e:
        print "socket.herror", e
        time.sleep(10)
        continue
      except socket.gaierror, e:
        print "socket.gaierror", e
        time.sleep(10)
        continue
      except socket.timeout, e:
        print "socket.timeout", e
        continue
      except socket.error, e:
        print "socket.error", e
        time.sleep(10)
        continue
      except Exception, e:
        tm=time.strftime("%Y.%m.%d-%H:%M:%S")
        print "%s Error: %s"%(tm, str(e))
        time.sleep(10)
        continue
      if STATUS_TO_TERMINAL==True:
        tm=time.strftime("%Y.%m.%d-%H:%M:%S")
        print "%s Die Verbindung zum CallMonitor der Fritzbox wurde hergestellt!"%(tm)

      while True: # Socket-Receive-Loop
        try:
          ln=self.recSock.recv(256).strip()
        except:
          ln=""

        if ln!="":
          self.fb_queue.put(ln)
        else:
          if STATUS_TO_TERMINAL==True:
            tm=time.strftime("%Y.%m.%d-%H:%M:%S")
            print "%s Die Verbindung zum CallMonitor der Fritzbox ist abgebrochen!"%(tm)
          self.fb_queue.put("CONNECTION_LOST")
          break   # zurück in die Socket-Connect-Loop

  # ###########################################################
  # Läuft als Thread.
  # Meldungen von der Queue empfangen, ggf. in Datenbank ablegen
  # und NOTIFY an alle verbundenen CallMonitor-Clients senden.
  # Funktion verändert:
  #   Datenbank
  #   self.fb_queue
  def runMessageToDatabase(self):
    # ein Thread braucht sein eigenes DB-Objekt, weil gemäß SQLite3-Doku gilt:
    # "...Python module disallows sharing connections and cursors between threads."
    # Die "fb_queue" wird in MessageToDatabase benötigt, damit der 11880-Query
    # nachträglich melden kann, dass [jetzt] ein Namen zur Nummer in der DB verfügbar
    # ist und die Clients neu einlesen können.
    self.m2db=MessageToDatabase(USE_11880_QUERIES, self.fb_queue, OWN_AREA_CODE)
    while True:
      msgtxt=self.fb_queue.get()
      if not (msgtxt=="CONNECTION_LOST" or msgtxt=="REFRESH"):
        self.m2db.addMessage(msgtxt)
      self.sendToAllConnectedClients("NOTIFY,%s"%(msgtxt))

  # ###########################################################
  # Sendet "strg" über den Notification-Socket an alle
  # verbundenen CallMonitor-Clients.
  def sendToAllConnectedClients(self, strg):
    for sock in self.connectedNotificationSockets:  # über alle verbundenen Clients
      self.sendAndIgnoreErrors(sock, strg)          # senden

  # ###########################################################
  # Kommandos von den verbundenen CallMonitor-Clients empfangen
  # und verarbeiten.
  #
  # Basiert in der groben Struktur auf:
  # http://www.ibm.com/developerworks/linux/tutorials/l-pysocks/#N10518
  #
  # in:   READ_PHONEBOOKS,Passwort
  # out:  ERROR | DONE
  #
  # in:   GET_FINISHED_CALLS,AnzahlZeilen
  # out:  ERROR | Zeilen
  #
  # in:   GET_OPEN_CALLS
  # out:  ERROR | Zeilen
  #
  # in:   GET_CALLS_FOR,Telefonnummer
  # out:  ERROR | Zeilen
  #
  # in:   FIND_CALLS_FOR,Suchbegriff
  # out:  ERROR | Zeilen
  #
  # in:   GET_OWN_AREA_CODE
  # out:  <OWN_AREA_CODE>
  #
  # in:   irgendwasAnderes
  # out:  UNKNOWN_COMMAND
  def runServer(self):
    self.srvSock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.srvSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
      self.srvSock.bind(("", self.port))
      self.srvSock.listen(5)
    except Exception, e:
      tm=time.strftime("%Y.%m.%d-%H:%M:%S")
      print "%s Kann Socket %d nicht öffnen:"%(tm, self.port), e
      return

    self.connectedNotificationSockets=[]        # Liste mit den Meldungs-Sockets
    self.connectedClientSockets=[self.srvSock]  # Liste mit den Steuer-Sockets und dem Listening-Socket
    SsockCountOld=MsockCountOld=-1              # Merker für die SocketAnzahl, um nur bei Änderung auszugeben
    status_strg="%s Anweisungs-Sockets=%d  Meldungs-Sockets=%d  Clients=%s"

    while True:
      if STATUS_TO_TERMINAL==True:
        SsockCount=len(self.connectedClientSockets)-1       # der -1 rechnet den Listening-Socket raus
        MsockCount=len(self.connectedNotificationSockets)
        tm=time.strftime("%Y.%m.%d-%H:%M:%S")
        if SsockCount!=SsockCountOld or MsockCount!=MsockCountOld:  # wenn sich die Anzahl der verbundenen Sockets geändert hat
          (SsockCountOld, MsockCountOld)=(SsockCount, MsockCount)   # neue Anzahl merken
          print status_strg%(tm, SsockCount, MsockCount, self.__getAllConnectedClientAliasNumbers())  # und neuen Status ausgeben

      (rlist, wlist, xlist)=select.select(self.connectedClientSockets, [], [])  # auf Verbindungen warten

      tm=time.strftime("%Y.%m.%d-%H:%M:%S")
      for sock in rlist:
        if sock==self.srvSock:                  # bei neuem Client-Connect
          clientname=self.newClientConnection() # Client annehmen
          if clientname!=None:
            self.__updateClientAlias(clientname)
            if STATUS_TO_TERMINAL==True:
              print "%s connect: %s alias Client[%d]"%(tm, clientname, self.clientalias.get(clientname, -1))
        else:
          clientname=self.findClient(sock)
          if clientname==None:
            continue
          Ssock, Msock=self.clients[clientname]

          if Msock==None:
            # da fehlt offenbar der Meldungs-Socket -> der Client hält sich nicht ans Protokoll
            self.connectedClientSockets.remove(Ssock) # ersten Socket zum Client wieder wegschmeißen
            Ssock.close()
            del self.clients[clientname]    # und Client vergessen
            continue                                    

          try:
            strg=sock.recv(1024)      # Kommando von Client empfangen
          except:
            strg=""                   # Client bei Fehler rausschmeißen

          if strg=="":                # wenn Client disconnected wurde
            if STATUS_TO_TERMINAL==True:
              print "%s disconnect: %s alias Client[%d]"%(tm, clientname, self.clientalias.get(clientname, -1))
            self.connectedClientSockets.remove(Ssock) # alle Sockets zum Client weg
            self.connectedNotificationSockets.remove(Msock)
            Ssock.close()
            Msock.close()
            del self.clients[clientname]
          else:                       # der Client will was
            msg=strg.strip().split(",", 1)  # ggf. Kommando-Parameter abtrennen
            #assert: len(msg)>=1
            if STATUS_TO_TERMINAL==True:
              print "%s Anweisung von Client[%d] empfangen: %s"%(tm, self.clientalias.get(clientname, -1), msg)
            if msg[0]=="READ_PHONEBOOKS":  # parameter=Fritzbox-Passwort
              if len(msg)!=2:
                self.sendAndIgnoreErrors(sock, "ERROR")
              else:
                fbpb=Phonebook(self.crypto.decrypt(msg[1]), FRITZBOX_IP)
                err, pbIDlist=fbpb.getPhonebookList() # Telefonbuch-IDs holen
                if err==True:
                  self.sendAndIgnoreErrors(sock, "ERROR")
                else:
                  self.sendAndIgnoreErrors(sock, "DONE")
                  self.getPhonebook(fbpb, pbIDlist)
            elif msg[0]=="GET_FINISHED_CALLS":  # parameter=Anzahl
              if len(msg)!=2:
                self.sendAndIgnoreErrors(sock, "ERROR")
              else:
                rows=self.db.getRowsFromLogFinished(int(msg[1]))
                self.sendMoreDataToSocket(sock, rows)
            elif msg[0]=="GET_OPEN_CALLS":  # parameter=<kein>
              rows=self.db.getRowsFromLog()
              self.sendMoreDataToSocket(sock, rows)
            elif msg[0]=="GET_CALLS_FOR":  # parameter=Nummer (ext)
              if len(msg)!=2:
                self.sendAndIgnoreErrors(sock, "ERROR")
              else:
                nrs=self.fixAreaCode([msg[1]])
                rows=[]
                for i in nrs:
                  rows+=self.db.getRowsForNumber(i)
                self.sendMoreDataToSocket(sock, rows)
            elif msg[0]=="FIND_CALLS_FOR":  # parameter=Suchbegriff
              if len(msg)!=2:
                self.sendAndIgnoreErrors(sock, "ERROR")
              else:
                rows=self.db.getRowsForNumberOrName(json.loads(msg[1]))
                self.sendMoreDataToSocket(sock, rows)
            elif msg[0]=="GET_OWN_AREA_CODE":
              self.sendAndIgnoreErrors(sock, OWN_AREA_CODE)
            else:
              self.sendAndIgnoreErrors(sock, "UNKNOWN_COMMAND")

  # ###########################################################
  # Sendet den Inhalt der Liste "dataList" an den Socket "sock"
  def sendMoreDataToSocket(self, sock, dataList):
    toSend=json.dumps(dataList)
    self.sendAndIgnoreErrors(sock, "%08d"%len(toSend))  # maximal 95MB ... das sollte erstmal langen
    self.sendAndIgnoreErrors(sock, toSend)

  # ###########################################################
  # Fügt einen "clientname" in self.clientalias ein.
  # Wird zur IP-Adresse in "clientname" nur genau ein Eintrag
  # in "self.clients" gefunden, bei dem auch die Port-Nummer
  # identisch zu der in "clientname" ist (der CallMon-Client
  # also nicht mehrfach auf dem System gestartet wurde), wird
  # ein Alias ggf. dadurch recycled, dass der Port-Anteil in
  # self.clientalias von einem Eintrag mit der IP-Adresse
  # gem. "clientname" durch die neue Port-Nummer in
  # "clientname" ersetzt wird.
  # Funktion verändert:
  #   self.clientalias
  def __updateClientAlias(self, clientname):
    if clientname in self.clientalias:  # clientname ist schon exakt genauso mit Alias drin...
      return                            # ... wird der Connect vom Meldungs-Socket gewesen sein

    hn, pn=clientname.split(":")
    # in "cnt" zählen, wie oft die IP-Adresse aus "clientname" in "self.clients" vorkommt
    cnt=0
    pm=""
    for k in self.clients.keys(): # über alle Keys ("IPaddr:port")
      h, p=k.split(":")           # zerlegen h=IPaddr, p=port
      if h==hn:                   # wenn IPaddr auf clientname passt
        cnt+=1                    # als Treffer zählen        
        pm=p                      # und Port merken (für den Fall, dass cnt==1 bleibt)

    done=False
    if cnt==1 and pm==pn:
      # IP-Adresse aus "clientname" kommt genau einmal in "self.clients" vor und die
      # Port-Nummer ist identisch - dann in "self.clientalias" nach einem recycle-baren
      # Satz suchen.
      km, vm=("", None)
      for k, v in self.clientalias.items(): # zu recyclenden Satz in "self.clientalias" suchen
        h, p=k.split(":")
        if h==hn:                           # wenn der Satz gefunden wurde...
          if km=="" or v<vm:                # ...und der Alias eine kleinere Nummer hat...
            km, vm=(k, v)                   # ...den nehmen
      if km!="":                            # wenn ein Satz gefunden wurde
        del self.clientalias[km]            # alten Satz löschen
        self.clientalias.update({clientname:vm})  # und mit neuer Port-Nummer wieder einfügen
        done=True

    if done==False:
      # IP-Adresse kommt mehrfach in "self.clients" vor
      # oder Port-Nummer aus "clientname" und "self.clients" sind nicht identisch
      # oder es wurde kein Satz mit recycle-barer IP-Adresse in "self.clientalias" gefunden
      l=len(self.clientalias)                 # nächsten freien Alias ermitteln
      self.clientalias.update({clientname:l}) # und einstellen

  # ###########################################################
  # Liefert in einem String eine Liste mit allen Aliasnummern
  # von den verbundenen Clients...zwecks Status-Anzeige.
  def __getAllConnectedClientAliasNumbers(self):
    rl=[]
    for k in self.clients.keys():
      rl.append(self.clientalias.get(k, -1))
    rl.sort()
    return(str(rl))

  # ###########################################################
  # Sendet "text" auf "sock" und ignoriert Fehler.
  def sendAndIgnoreErrors(self, sock, text):
    try:
      sock.send(text)
    except:
      pass

  # ###########################################################
  # Findet zu einem Steuer-Socket "socket" den Namen des Clients.
  def findClient(self, socket):
    for k, (s1, s2) in self.clients.items():
      if socket==s1:
        return(k)
    return(None)

  # ###########################################################
  # Nimmt eine Verbindung von einem neuen CallMonitor-Client
  # an. Pro Client werden zwei Sockets verwaltet, zuerst einer
  # zur Steuerung des Servers, dann einer für Meldungen an den
  # Client.
  # Bei der Rückmeldung für den Steuer-Socket übergibt der
  # Server seinen öffentlichen Schlüssel an den Client, mit dem
  # dieser ggf. das Fritzbox-Passwort vor der Übertragung zum
  # Server verschlüsseln muss.
  #
  # Kommunikations-Ablauf:
  #   Client sendet:  IamTheControlSocket,1.2.3.4:1234
  #   Server liefert: OK,blabla_public_key_blabla
  # oder:
  #   Client sendet:  IamTheNotificationSocket,1.2.3.4:1234
  #   Server liefert: OK,-
  #
  # Funktion verändert:
  #   self.connectedClientSockets
  #   self.connectedNotificationSockets
  #   self.clients
  def newClientConnection(self):
    newClientSocket, (remhost, remport)=self.srvSock.accept()   # Verbindung annehmen
    try:
      typ=newClientSocket.recv(256)   # erwartet: typKenner,eindeutigerName (als IPaddr:port)
    except:
      return(None)
    msg=typ.strip().split(",", 1)
    if len(msg)==2:
      if msg[0]=="IamTheControlSocket":
        pwd=self.crypto.getPublicKey()                            # öffentlichen Schlüssel für Client holen
        try:
          newClientSocket.send("OK,%s"%(pwd))                     # OK-Meldung + Schlüssel zurückliefern
        except:
          return(None)
        self.connectedClientSockets.append(newClientSocket)       # Steuer-Socket merken
        self.clients.update({msg[1]:(newClientSocket, None)})     # Client-Namen mit Socket merken
        return(msg[1])                                            # Client-Namen zurückliefern
      elif msg[0]=="IamTheNotificationSocket":
        try:
          newClientSocket.send("OK,-")                            # OK-Meldung zurückliefern
        except:
          return(None)
        s1, s2=self.clients.get(msg[1], (None, None))             # Client-Datensatz auslesen...
        if s1==None:
          return(None)                                            # NotificationSocket vor ControlSocket ist illegal
        self.connectedNotificationSockets.append(newClientSocket) # Meldungs-Socket merken
        self.clients.update({msg[1]:(s1, newClientSocket)})       # und um den neuen Socket erweitert zurückschreiben
        return(msg[1])                                            # Client-Namen zurückliefern
    return(None)                                                  # Fehler-Kennung zurückliefern

  # ###########################################################
  # Liest alle Telefonbücher mit den IDs aus "pbIDlist" von der
  # Fritzbox und schreibt deren aufbereiteten Inhalt in die
  # Datenbank.
  # Funktion verändert:
  #   Datenbank
  def getPhonebook(self, fbpb, pbIDlist):
    pbd={}
    for pbid in pbIDlist:                           # über alle Telefonbuch-IDs
      rc, data=fbpb.getPhonebook(pbid)              # Telefonbuch(ID) holen
      pb_dict=ParseXML_Phonebook(data).get()        # Telefonbuch nach Dictionary wandeln
      for name, (fbid, numbers) in pb_dict.items(): # über alle Einträge des Dictionaries
        #print name, fbid, numbers
        numbers=self.fixAreaCode(numbers)           # ggf. fixen bzw. erweitern
        pbd.update({name:(fbid, numbers)})          # und für die Übergabe an DB merken
    self.db.updatePhonebook(pbd)                    # gemerktes Telefonbuch in DB schreiben
    # wird ein Gespräch just in dem Moment beendet, in dem der self.db.updatePhonebook() läuft,
    # werden die alten Namen/Nummern in die LogFinished-Tabelle geschrieben.
    # Der commit auf die DB erfolgt erst nach vollständigem Update.
    
  # ###########################################################
  # Prüft für allen Telefonnummern in "numbers", ob sie nicht
  # mit einer 0 beginnen und fügt der Liste in diesem Fall die
  # Nummer nochmal mit vorangestellter Vorwahl zu.
  #
  # Beginnt die Telefonnummer in "numbers" mit der eigenen
  # Vorwahl, wird die Nummer nochmal ohne Vorwahl zugefügt.
  #
  # Dadurch kann auch dann einer anrufenden Telefonnummer ein
  # Name zugeordnet werden, wenn die Nummer im Telefonbuch der
  # Fritzbox nur ohne Vorwahl steht - und analog für ausgehende
  # Telefonate, die ohne Vorwahl gewählt werden, aber im
  # Telefonbuch der Fritzbox mit Vorwahl drinstehen.
  def fixAreaCode(self, numbers):
    if OWN_AREA_CODE=="":
      return(numbers)

    nrSet=set()
    for nr in numbers:
      nrSet.add(nr)
      if nr[:1] in ("1", "2", "3", "4", "5", "6", "7", "8", "9"): # wenn Nummer nicht mit 0 beginnt (also ohne Vorwahl)...
        nrSet.add(OWN_AREA_CODE+nr)                               # ...dann Nummer nochmal mit Vorwahl einfügen
      if nr[:len(OWN_AREA_CODE)]==OWN_AREA_CODE:                  # wenn Nummer mit der eigenen Vorwahl beginnt...
        nrSet.add(nr[len(OWN_AREA_CODE):])                        # ...dann Nummer nochmal ohne Vorwahl einfügen
    return(list(nrSet))



if __name__=='__main__':
  myServer=CallMonServer(CALLMON_SERVER_SOCKET)
  myServer.runServer()

