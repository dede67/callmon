#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3    # sqlite3-3.7.12.1-2.1.2.x86_64
import os
import datetime

from CallMonitorMessage import CallMonitorMessage
from MsgTyp import MsgTyp

HOMEDIR=os.path.expanduser('~')
DATABASENAME=os.path.join(HOMEDIR, ".callmon.sqlite")


# ###########################################################
# DB-Zugriff für die Telefonbücher und Verbindungsdaten.
class Database():
  def __init__(self, own_area_code=""):
    self.dbname=DATABASENAME
    self.own_area_code=own_area_code
    self.msgtyp=MsgTyp()

    if os.path.exists(self.dbname)==False:      # wenn Datenbank-Datei noch nicht existiert -> neu anlegen
      self.connection=sqlite3.connect(self.dbname)
      self.connection.text_factory=sqlite3.OptimizedUnicode
      cursor=self.connection.cursor()

      cursor.execute('CREATE TABLE Names' \
                          ' (ID        INTEGER NOT NULL PRIMARY KEY,' \
                          '  fbID      INTEGER,' \
                          '  name      VARCHAR NOT NULL UNIQUE)')
      cursor.execute('CREATE UNIQUE INDEX Names_fbID_idx ON Names (fbID ASC)')

      cursor.execute('CREATE TABLE Numbers' \
                          ' (ID        INTEGER NOT NULL PRIMARY KEY,' \
                          '  NamesID   INTEGER NOT NULL,' \
                          '  number    VARCHAR)')
      cursor.execute('CREATE UNIQUE INDEX Numbers_number_idx  ON Numbers (number ASC)')
      cursor.execute('CREATE        INDEX Numbers_NamesID_idx ON Numbers (NamesID ASC)')
      # in der Fritzbox ist das Feld "number" NICHT unique!

      cursor.execute('CREATE TABLE Log' \
                          ' (ID        INTEGER NOT NULL PRIMARY KEY,' \
                          ' tmstmp     TEXT,' \
                          ' typ        TEXT,' \
                          ' conid      TEXT,' \
                          ' tel        TEXT,' \
                          ' tel_pb     TEXT,' \
                          ' num_int    TEXT,' \
                          ' num_ext    TEXT,' \
                          ' dur        TEXT,' \
                          ' sip        TEXT,' \
                          ' finished   TEXT)')

      cursor.execute('CREATE VIEW LogWithNames AS' \
                          ' SELECT  l.ID, tmstmp, typ, conid, tel, tel_pb, na1.name AS tel_name,' \
                          '        num_int, num_ext, na2.name AS num_ext_name, dur, sip, finished' \
                          ' FROM Log l LEFT OUTER JOIN Numbers nu1 ON l.tel_pb=nu1.number' \
                          '            LEFT OUTER JOIN Names   na1 ON nu1.NamesID=na1.ID' \
                          '            LEFT OUTER JOIN Numbers nu2 ON l.num_ext=nu2.number' \
                          '            LEFT OUTER JOIN Names   na2 ON nu2.NamesID=na2.ID')

      cursor.execute('CREATE VIEW NamesAndNumbers AS' \
                          ' SELECT na.ID, na.fbID, na.name, nu.number FROM Names na, Numbers nu' \
                          ' WHERE nu.NamesID=na.ID')

      cursor.execute('CREATE TABLE LogFinished' \
                          ' (ID           INTEGER NOT NULL PRIMARY KEY,' \
                          ' tmstmp_start  TEXT,' \
                          ' tmstmp_end    TEXT,' \
                          ' typ_seq       TEXT,' \
                          ' conid         TEXT,' \
                          ' tel           TEXT,' \
                          ' tel_pb        TEXT,' \
                          ' tel_name      TEXT,' \
                          ' num_int       TEXT,' \
                          ' num_ext       TEXT,' \
                          ' num_ext_name  TEXT,' \
                          ' dur           TEXT,' \
                          ' sip           TEXT)')
      # Die Tabelle "LogFinished" enthält die (vermeintlich überflüssigen) Spalten "tel_name"
      # und "num_ext_name" deswegen, um bei Änderungen am Telefonbuch damit nicht [möglicherweise]
      # gleichzeitig die Vergangenheit zu ändern ... was ja der Fall wären, wenn "Names" ge-joined würde.
      cursor.execute('CREATE INDEX LogFinished_tmstmp_start_idx ON LogFinished (tmstmp_start ASC)')

      cursor.execute('CREATE TABLE Names11880' \
                          ' (ID        INTEGER NOT NULL PRIMARY KEY,' \
                          '  number    TEXT,' \
                          '  name      TEXT,' \
                          '  expires   TEXT)')
      cursor.execute('CREATE INDEX Names11880_number_idx  ON Names11880 (number ASC)')
      cursor.execute('CREATE INDEX Names11880_expires_idx ON Names11880 (expires ASC)')

      self.connection.commit()
    else:
      self.connection=sqlite3.connect(self.dbname)

  # ###########################################################
  # Liefert das Telefonbuch aus der Datenbank als Dictionary.
  # Format ist: {name : (fbID, [nummer, nummer, ...]), ...}
  def getPhonebookAsDictionary(self):
    rd={}
    c1=self.connection.cursor()
    c2=self.connection.cursor()
    c1.execute('SELECT ID, fbID, name FROM Names')
    name=c1.fetchone()
    while name!=None:               # über alle Namen
      c2.execute('SELECT number FROM Numbers WHERE NamesID=?', (name[0], ))
      numbers_raw=c2.fetchall()     # alle Nummern zum jew. Namen
      numbers=[]
      for i in numbers_raw:
        numbers.append(i[0])        # Nummern-Liste hübscher formatieren
      #print "name=", name, "numbers=", numbers
      rd.update({name[2] : (name[1], numbers)}) # ins Dictionary damit
      name=c1.fetchone()
    return(rd)

  # ###########################################################
  # Aktualisiert ein Telefonbuch-Dictionary "pb_dict" so in der
  # Datenbank, dass nur bei tatsächlichen Änderungen neue Sätze
  # angelegt oder alte Sätze gelöscht werden.
  def updatePhonebook(self, pb_dict):
    pb_dict_cur=self.getPhonebookAsDictionary() # derzeitigen Inhalt aus der DB holen
    # Format ist: name : (fbID, [nummer, nummer, ...])

    pbk_cur=self.__rekeyPhonebookDictionary(pb_dict_cur)  # Key in Dict auf fbID ändern
    pbk_new=self.__rekeyPhonebookDictionary(pb_dict)
    # Format ist: fbID : (name, [nummer, nummer, ...])

    cursor=self.connection.cursor()
    # Loop 1 fügt ggf. neue Einträge ein oder aktualisiert vorhandene
    for fbid, (name, numbers) in pbk_new.items(): # über alle Einträge aus der Fritzbox
      if fbid in pbk_cur:                         # wenn die fbid schon in der DB ist
        if name!=pbk_cur[fbid][0]:                # der Name aber nicht gleich ist
          cursor.execute('UPDATE Names SET name=? WHERE fbID=?', (name, fbid))  # Namen setzen

        nr_new=set(numbers)                       # Menge der Nummern zum Namen laut Fritzbox
        nr_cur=set(pbk_cur[fbid][1])              # Menge der Nummern zum Namen laut Datenbank
        if nr_new!=nr_cur:                        # wenn Nummern-Mengen ungleich sind
          cursor.execute('SELECT ID FROM Names WHERE fbID=?', (fbid, )) # dann wird die DB-ID gebraucht
          names_id=cursor.fetchone()[0]           # DB-ID zum Namen holen
          nr_2add=nr_new-nr_cur                   # Menge der hinzuzufügenden Nummern zum Namen
          nr_2del=nr_cur-nr_new                   # Menge der zu entfernenden Nummern zum Namen
          for nr in nr_2add:
            try:
              cursor.execute('INSERT INTO Numbers (NamesID, number) VALUES (?, ?)', (names_id, nr))
            except:
              # number kommt mehrfach vor
              print "Fehler in Numbers:", name, fbid, numbers, nr
              continue

          for nr in nr_2del:
            cursor.execute('DELETE FROM Numbers WHERE NamesID=? AND number=?', (names_id, nr))
      else:                                       # die fbid ist noch nicht in DB
        try:
          cursor.execute('INSERT INTO Names (name, fbID) VALUES (?, ?)', (name, fbid))
        except:
          # name kommt mehrfach vor
          print "Fehler in Names:", name, fbid, numbers
          continue
        cursor.execute('SELECT ID FROM Names WHERE fbID=?', (fbid, ))
        names_id=cursor.fetchone()[0]
        for nr in numbers:
          try:
            cursor.execute('INSERT INTO Numbers (NamesID, number) VALUES (?, ?)', (names_id, nr))
          except:
            # number kommt mehrfach vor
            print "Fehler in Numbers:", name, fbid, numbers, nr
            continue


    # Loop 2 löscht ggf. nicht mehr vorhandene Einträge
    for fbid, (name, numbers) in pbk_cur.items(): # über alle Einträge aus der Datenbank
      if fbid not in pbk_new:                     # wenn die fbid nicht in der Fritzbox ist
        cursor.execute('SELECT ID FROM Names WHERE fbID=?', (fbid, )) # DB-ID bestimmen
        names_id=cursor.fetchone()[0]
        cursor.execute('DELETE FROM Names WHERE ID=?', (names_id, ))  # und weg damit
        cursor.execute('DELETE FROM Numbers WHERE NamesID=?', (names_id, ))
    self.connection.commit()

  # ###########################################################
  # Liefert eine Version von "pb_dict", bei der name und fbID
  # ausgetauscht sind - also fbID Key ist.
  # Format ist: {fbID : (name, [nummer, nummer, ...]), ...}
  def __rekeyPhonebookDictionary(self, pb_dict):
    new_dict={}
    for name, (fbid, numbers) in pb_dict.items():
      new_dict.update({fbid:(name, numbers)})
    return(new_dict)

  # ###########################################################
  # Liefert zu einer (externen) Telefonnummer ggf. den im
  # Telefonbuch hinterlegten Namen. Wird kein Name zur Nummer
  # gefunden, wird die Nummer geliefert.
  def getNameFromNumber(self, number):
    cursor=self.connection.cursor()
    cursor.execute('SELECT name FROM Names, Numbers WHERE NamesID=Names.ID AND number=?', (number, ))
    c=cursor.fetchone() # c[0]=name
    if c==None:
      rc=number
    else:
      rc=c[0]
    return(rc)

  # ###########################################################
  # Liefert zu einer (externen) Telefonnummer den im
  # 11880-Telefonbuch ggf. hinterlegten Namen und dessen
  # Ablauf-Status als:
  #   ("name", True)  = Name enthalten aber abgelaufen
  #   ("name", False) = Name enthalten und gültig
  #   (None, True)    = Name nicht enthalten
  def getName11880FromNumber(self, number):
    if self.own_area_code!="" and number[:1] in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
      number=self.own_area_code+number

    cursor=self.connection.cursor()
    cursor.execute('SELECT name, expires FROM Names11880 WHERE number=?', (number, ))
    c=cursor.fetchone() # c[0]=name, c[1]=expires
    if c==None:
      rc=(None, True) # unbekannt und abgelaufen
    else:
      today=datetime.date.today().strftime("%Y.%m.%d")
      rc=(c[0], c[1]<=today)
    return(rc)

  # ###########################################################
  # Schreibt "name" zu "number" in die Tabelle "Names11880".
  def insertOrUpdateNames11880(self, name, number):
    today=datetime.date.today().strftime("%Y.%m.%d")
    expires=(datetime.date.today()+datetime.timedelta(30)).strftime("%Y.%m.%d")  # Name ist nach 30 Tagen abgelaufen
    cursor=self.connection.cursor()

    n, e=self.getName11880FromNumber(number)
    if n==None:       # wenn name nicht da
      cursor.execute('INSERT INTO Names11880 (number, name, expires) VALUES (?, ?, ?)', (number, name, expires))
      self.connection.commit()
    elif e==True:     # wenn name da, aber abgelaufen
      cursor.execute('UPDATE Names11880 SET name=?, expires=? WHERE number=?', (name, expires, number))
      self.connection.commit()

  # ###########################################################
  # Fügt einen Satz mit einer CallMonitorMessage in die Tabelle
  # Log ein. Ist der eingefügte Satz eine "DISCONNECT"-Meldung,
  # wird sofort (ohne COMMIT zwischendurch) nach LogFinished
  # kopiert.
  def insertLog(self, msg):
    cursor=self.connection.cursor()
    cursor.execute('INSERT INTO Log' \
                   ' (tmstmp, typ, conid, tel, tel_pb, num_int, num_ext, dur, sip, finished)' \
                   ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                   (msg.tmstmp, msg.typ, msg.conid, msg.tel, msg.tel_pb, msg.num_int, msg.num_ext, msg.dur, msg.sip, msg.finished))
    if msg.typ=="DISCONNECT":   # wenn Telefonat abgeschlossen ist
      self.updateLogFinished()  # gleich umkopieren
    else:
      self.connection.commit()

  # ###########################################################
  # Fügt einen Satz mit einer CallMonitorMessage in die Tabelle
  # LogFinished ein.
  # OHNE COMMIT !
  def __insertLogFinished(self, msg):
    cursor=self.connection.cursor()
    cursor.execute('INSERT INTO LogFinished' \
                   ' (tmstmp_start, tmstmp_end, typ_seq, conid, tel, tel_pb, tel_name, num_int, num_ext, num_ext_name, dur, sip)' \
                   ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                   (msg.tmstmp, msg.tmstmp2, msg.typ, msg.conid, msg.tel, msg.tel_pb, msg.tel_name, 
                    msg.num_int, msg.num_ext, msg.num_ext_name, msg.dur, msg.sip))

  # ###########################################################
  # Überträgt einen DB-Satz "c" aus LogWithNames in ein
  # CallMonitorMessage-Objekt und liefert dieses zurück.
  # Darf nur bei RING- oder CALL-Meldungen aufgerufen werden.
  def __fillCallMonitorMessage(self, c):
    msg=CallMonitorMessage()
    msg.tmstmp=c[1]
    if c[2]=="RING":
      msg.typ+=self.msgtyp.ring
    elif c[2]=="CALL":
      msg.typ+=self.msgtyp.call
    else:
      print "__fillCallMonitorMessage: illegaler Aufruf!", c[2]
    msg.conid=c[3]
    msg.tel=c[4]
    msg.tel_pb=c[5]
    if c[6]==None:      # NULL ...
      msg.tel_name=u""  # ... nach ""
    else:
      msg.tel_name=c[6]
    msg.num_int=c[7]
    msg.num_ext=c[8]
    if c[9]==None:                                  # wenn join zum Fritzbox-Telefonbuch nix geliefert hat
      n, e=self.getName11880FromNumber(msg.num_ext) # im 11880-Telefonbuch nachsehen...
      if n!=None:
        msg.num_ext_name=n                          # ...und einsetzen
      else:
        msg.num_ext_name=u""                        # ...bzw. auf <leer> setzen, wenn dort auch kein Name drin ist
    else:
      msg.num_ext_name=c[9]                         # Namen aus dem Fritzbox-Telefonbuch einsetzen
    msg.dur=c[10]
    msg.sip=c[11]
    msg.finished=c[12]
    return(msg)

  # ###########################################################
  # Setzt bei allen Sätzen aus Log, deren ID in "idlst"
  # vorkommt, das Feld finished auf "fin".
  # ...oder löscht - was gerade nicht auskommentiert ist.
  # OHNE COMMIT !
  def __updateLogSetFinished(self, idlst, fin):
    cursor=self.connection.cursor()
    for i in idlst:
      #cursor.execute('UPDATE Log SET finished=? WHERE ID=?', (fin, i))
      # Hier könnte statt UPDATE auch ein DELETE stehen....
      # Die Sätze werden eigentlich nicht mehr gebraucht.
      # Für Debug-Zwecke wird aber erstmal alles aufbewahrt.
      cursor.execute('DELETE FROM Log WHERE ID=?', (i, ))

  # ###########################################################
  # Überträgt alle fertigen Sequenzen bestehend aus
  #       RING|CALL + [CONNECT] + DISCONNECT
  # von der Tabelle Log nach LogFinished und markiert die
  # kopierten Sätze in Log mit finished=X (bzw. löscht sie).
  #
  # Bei illegalen Sequenzen (CONNECT ohne vorherigen RING|CALL)
  # wird statt des X ein Fehler-Marker ins Feld finished
  # gesetzt (bzw. gelöscht).
  #
  # Bei RING|CALL + [CONNECT] + RING|CALL wird ein Fehler-Marker
  # ins Feld finished der ersten Sequenz gesetzt (bzw. gelöscht).
  #
  # Die Sequenz RING|CALL + CONNECT + CONNECT wird nicht
  # abgefangen bzw. überschreibt der zweite CONNECT den ersten
  # und liefert msg.typ = "-> bla bla" oder "<- bla bla".
  #
  # Sequenzen von RING|CALL + [CONNECT] ohne DISCONNECT "am
  # Ende" der Tabelle Log werden nicht verändert (solange die
  # conid ungenutzt bleibt).
  def updateLogFinished(self):
    cursor=self.connection.cursor()
    #                      0    1      2     3     4     5      6         7        8        9             10   11   12
    cursor.execute('SELECT ID, tmstmp, typ, conid, tel, tel_pb, tel_name, num_int, num_ext, num_ext_name, dur, sip, finished' \
                        ' FROM LogWithNames WHERE finished="" ORDER BY ID ASC')
    c=cursor.fetchone()
    open_conids=[]      # Format: [conid1, conid2, ...]
    open_connections={} # Format: {conid1:(msg1, idlst1), conid2:(msg2, idlst2), ...}
    while c!=None:
      if c[2] in ("RING", "CALL"):  # ----------------------------------------------------------------------------
        if open_conids.count(c[3])>0:                               # conid bereits offen -> Fehler!
          print "conid bereits offen -> Fehler!", open_conids
          msg, idlst=open_connections.get(c[3], (None, None))       # alte Message laden,
          self.__updateLogSetFinished(idlst, "Err(no DISCONNECT)")  # auf Fehler setzen und
          open_conids.remove(c[3])                                  # hier wegschmeißen
        open_conids.append(c[3])                                    # conid als offen merken
        msg=self.__fillCallMonitorMessage(c)                        # Message nach "msg" parsen
        open_connections.update({c[3]:(msg, [c[0]])})               # conid mit msg und DB-ID merken
      elif c[2]=="CONNECT":         # ----------------------------------------------------------------------------
        if open_conids.count(c[3])!=1:                              # conid nicht offen -> Fehler!
          print "conid nicht offen -> Fehler!", open_conids
          self.__updateLogSetFinished([c[0]], "Err(no RING|CALL)")  # aktuelle Message auf Fehler setzen
        else:
          msg, idlst=open_connections.get(c[3], (None, None))       # Daten der RING|CALL-Message holen
          # Hier könnte len(idlst)>1 geprüft werden, um damit Sequenzen RING|CALL + CONNECT + CONNECT zu erkennen.
          # Allerdings müssten in diesem Fall alle Teile der Sequenz weggeschmissen werden. Daher wirds nicht
          # gemacht - und vielleicht wird die zweite CONNECT-Meldung von AVM ja mal für Gesprächsweitergabe genutzt.
          if msg!=None:
            idlst.append(c[0])                                      # DB-ID merken
            msg.typ+=self.msgtyp.connect                            # "bla" anhängen
            msg.tel=c[4]                                            # msg um Infos erweitern
            msg.tel_pb=c[5]
            if c[6]==None:                                          # wenn DB einen NULL liefert
              msg.tel_name=""                                       # umsetzen nach Leerstring
            else:
              msg.tel_name=c[6]                                     # ansonsten Wert einsetzen
      elif c[2]=="DISCONNECT":      # ----------------------------------------------------------------------------
        if open_conids.count(c[3])!=1:                              # conid nicht offen -> Fehler!
          print "conid nicht offen -> Fehler!", open_conids
          self.__updateLogSetFinished([c[0]], "Err(no RING|CALL)")  # aktuelle Message auf Fehler setzen
        else:
          open_conids.remove(c[3])                                  # conid löschen
          msg, idlst=open_connections.get(c[3], (None, None))       # bisherige msg zur conid holen
          if msg!=None:
            idlst.append(c[0])                                      # DB-ID merken
            msg.tmstmp2=c[1]                                        # Ende-Zeit setzen (braucht keiner aber egal)
            msg.typ+=self.msgtyp.disconnect                         # "-X" anhängen
            msg.dur=c[10]                                           # Dauer setzen
            if msg.num_ext_name=="":                                # wenn kein Name im Fritzbox-Telefonbuch gefunden wurde
              n, e=self.getName11880FromNumber(msg.num_ext)         # im 11880-Telefonbuch suchen
              if n!=None:                                           # wenn drin (egal ob abgelaufen oder nicht)
                msg.num_ext_name=n                                  # einstellen
            self.__insertLogFinished(msg)                           # msg nach LogFinished schreiben
            self.__updateLogSetFinished(idlst, "X")                 # und in Log als bearbeitet markieren bzw. löschen
      else:
        print "Datenbank-Fehler: unbekannter Meldungs-Typ in Nachricht vom Fritzbox-CallMonitor!"
      c=cursor.fetchone()
    self.connection.commit()

  # ###########################################################
  # Liefert die "count" neusten Sätze aus LogFinished.
  # Bei "count"<=0 werden alle Sätze geliefert.
  def getRowsFromLogFinished(self, count):
    cursor=self.connection.cursor()
    #                      0             1        2    3         4        5        6             7    8      9
    cursor.execute('SELECT tmstmp_start, typ_seq, tel, tel_name, num_int, num_ext, num_ext_name, dur, conid, tel_pb' \
                   ' FROM LogFinished ORDER BY tmstmp_start DESC')
    c=cursor.fetchone()
    ret_lst=[]
    while c!=None:
      ret_lst.append(c)
      if count>0:           # nur wenn count von außen als >0 reinkommt...
        count-=1            # ...count überhaupt dekementieren...
        if count<=0:        # ...und auf <=0 prüfen...
          break             # ...um dann ggf. die Schleife zu verlassen
      c=cursor.fetchone()
    return(ret_lst)

  # ###########################################################
  # Liefert die 100 neusten Sätze aus LogFinished mit der
  # Nummer "number".
  def getRowsForNumber(self, number):
    cursor=self.connection.cursor()
    #                      0             1        2    3         4        5        6             7    8      9
    cursor.execute('SELECT tmstmp_start, typ_seq, tel, tel_name, num_int, num_ext, num_ext_name, dur, conid, tel_pb' \
                   ' FROM LogFinished WHERE num_ext=? ORDER BY tmstmp_start DESC', (number, ))
    c=cursor.fetchone()
    ret_lst=[]
    count=100
    while c!=None:
      ret_lst.append(c)
      count-=1
      if count<=0:
        break
      c=cursor.fetchone()
    return(ret_lst)

  # ###########################################################
  # Liefert die 100 neusten Sätze aus LogFinished, bei denen
  # "searchFor" per LIKE-Suche auf die Spalten num_ext oder
  # num_ext_name passt.
  def getRowsForNumberOrName(self, searchFor):
    cursor=self.connection.cursor()
    #                      0             1        2    3         4        5        6             7    8      9
    cursor.execute('SELECT tmstmp_start, typ_seq, tel, tel_name, num_int, num_ext, num_ext_name, dur, conid, tel_pb' \
                   ' FROM LogFinished WHERE num_ext LIKE ? OR num_ext_name LIKE ? ORDER BY tmstmp_start DESC', (searchFor, searchFor))
    c=cursor.fetchone()
    ret_lst=[]
    count=100
    while c!=None:
      ret_lst.append(c)
      count-=1
      if count<=0:
        break
      c=cursor.fetchone()
    return(ret_lst)

  # ###########################################################
  # Liefert die noch offenen Gespräche.
  def getRowsFromLog(self):
    cursor=self.connection.cursor()
    #                      0    1      2     3     4     5      6         7        8        9             10   11   12
    cursor.execute('SELECT ID, tmstmp, typ, conid, tel, tel_pb, tel_name, num_int, num_ext, num_ext_name, dur, sip, finished' \
                   ' FROM LogWithNames WHERE finished="" ORDER BY ID ASC')
    c=cursor.fetchone()
    open_conids=[]      # Format: [conid1, conid2, ...]
    open_connections={} # Format: {conid1:msg1, conid2:msg2, ...}
    while c!=None:
      if c[2] in ("RING", "CALL"):  # ----------------------------------------------------------------------------
        if open_conids.count(c[3])>0:                               # conid bereits offen -> Fehler!
          print "conid bereits offen -> Fehler!", open_conids
          open_conids.remove(c[3])                                  # conid wegschmeissen, um sie neu anhängen zu können
        open_conids.append(c[3])                                    # conid als offen merken
        msg=self.__fillCallMonitorMessage(c)                        # Message nach "msg" parsen
        open_connections.update({c[3]:msg})                         # conid mit msg merken
      elif c[2]=="CONNECT":         # ----------------------------------------------------------------------------
        if open_conids.count(c[3])!=1:                              # conid nicht offen -> Fehler!
          print "conid nicht offen -> Fehler!", open_conids
        else:
          msg=open_connections.get(c[3], None)                      # Daten der RING|CALL-Message holen
          if msg!=None:
            msg.typ+=unicode(self.msgtyp.connect)                   # "bla" anhängen
            msg.tel=c[4]                                            # msg um Infos erweitern
            msg.tel_pb=c[5]
            if c[6]==None:                                          # wenn DB einen NULL liefert
              msg.tel_name=u""                                      # umsetzen nach Leerstring
            else:
              msg.tel_name=c[6]                                     # ansonsten Wert einsetzen
      elif c[2]=="DISCONNECT":      # ----------------------------------------------------------------------------
        # Ein DISCONNECT sollte hier eigentlich nicht vorkommen.....
        # Der insertLog(msg) startet bei einer DISCONNECT-Meldung direkt updateLogFinished() - ohne zwischendurch
        # einen COMMIT an die DB zu schicken.
        # Damit stehen zu keinem Zeitpunkt commit'ete DISCONNECT-Meldungen mit finished="" in der Log-Tabelle und
        # folglich auch nicht in dem VIEW LogWithNames.
        print "...sonderbar...sonderbar...hier sollte er nicht hinkommen können!"
        if open_conids.count(c[3])!=1:        # conid nicht offen -> Fehler!
          print "conid nicht offen -> Fehler!", open_conids
        else:
          open_conids.remove(c[3])            # conid freigeben
          del open_connections[c[3]]          # conid samt msg wegschmeißen (ist ja offenbar nicht mehr "offen")
      c=cursor.fetchone()
    ret_lst=[]
    for k, msg in open_connections.items():
      ret_lst.append((msg.tmstmp, msg.typ, msg.tel, msg.tel_name, msg.num_int, msg.num_ext, 
                      msg.num_ext_name, u"0", msg.conid, msg.tel_pb))
    return(ret_lst)

  # ###########################################################
  # Setzt alle offenen Sätze in der Tabelle Log auf Fehler
  # (bzw. löscht sie). Wird nur beim Start des CallMon-Servers
  # aufgerufen.
  def clearLogOnStartup(self):
    cursor=self.connection.cursor()
    cursor.execute('SELECT ID FROM Log WHERE finished=""')
    c=cursor.fetchone()
    idlst=[]
    while c!=None:
      idlst.append(c[0])
      c=cursor.fetchone()
    self.__updateLogSetFinished(idlst, "Err(restart)")
    self.connection.commit()
    return(len(idlst))

  # ###########################################################
  # Liefert eine Liste aus Tupeln von (ID, timestamp) der
  # Sätze, die auf den Löschbereich passen.
  def prepareDelete(self, date, isRange=False):
    cursor=self.connection.cursor()
    cursor.execute('SELECT count(*) FROM LogFinished')
    c=cursor.fetchone()
    allcnt=c[0]

    if isRange==True:
      cursor.execute('SELECT ID, tmstmp_start FROM LogFinished' \
                     ' WHERE tmstmp_start<? ORDER BY tmstmp_start DESC', (date, ))
    else:
      cursor.execute('SELECT ID, tmstmp_start FROM LogFinished' \
                     ' WHERE tmstmp_start LIKE ? ORDER BY tmstmp_start DESC', (date+'%', ))
    c=cursor.fetchall()
    if len(c)>0:
      return((allcnt, len(c), c[0][1], c[len(c)-1][1]))
    return((allcnt, 0, None, None))

  # ###########################################################
  # Löscht die Sätze, die auf den Löschbereich passen.
  def executeDelete(self, date, isRange=False):
    cursor=self.connection.cursor()

    if isRange==True:
      cursor.execute('DELETE FROM LogFinished WHERE tmstmp_start<?', (date, ))
    else:
      cursor.execute('DELETE FROM LogFinished WHERE tmstmp_start LIKE ?', (date+'%', ))
    self.connection.commit()



if __name__=='__main__':
  db=Database()  

  d=db.getPhonebookAsDictionary()
  for k, v in d.items():
    print k, v

