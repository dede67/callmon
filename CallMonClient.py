#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wx
import wx.lib.mixins.listctrl as listmix
import sys
import time
import socket
import select
import threading
import json
import lxml.html

from Queue              import Queue
from ConfigFile         import CfgFile
from MsgTyp             import MsgTyp
from MiniCryptoV2       import MiniCryptoV2
from SetupDialog        import SetupDialog
from HistoryDialog      import HistoryDialog
from PopupControl       import PopupControl
from CallMonitorMessage import CallMonitorMessage

# auf True, wenn das Fenster nicht in der Taskbar erscheinen soll. Sonst auf False
#FRAME_NO_TASKBAR=True
FRAME_NO_TASKBAR=False

# ###########################################################
# 16.11.2014  1.0   erste Version
# 23.11.2014  1.0.1 "REFRESH" eingebaut (für Namen von 11880, die erst nach dem NOTIFY eintreffen)
# 24.11.2014  1.0.2 selektierte Zeilen bleiben nach Umsortierung erhalten
# 26.11.2014  1.0.3 Abschaltbarkeit von Spalten via Menü eingebaut
# 26.11.2014  1.0.4 Umstellung auf MiniCryptoV2 (jetzt mit private/public-Keys)
# 27.11.2014  1.0.5 "GET_CALLS_FOR" bzw. HistoryDialog() eingebaut, Einstellung der Farben
#                   via Setup-Dialog eingebaut
# 07.12.2014  1.1   PopupControl statt wx.TipWindow
# 18.12.2014  1.1.1 Selektierung beim ersten Klick, De-Selektierung beim zweiten Klick
#                   durch OnFocused() und OnSelected() eingebaut,
#                   Korrektur bei Fensterposition lesen (war vom Panel statt vom Frame)
# 29.01.2014  1.1.2 Suchfunktion nach Nummer und Name eingebaut
# 25.02.2015  1.1.3 get_OWN_AREA_CODE() eingebaut und Verarbeitung der eigenen Vorwahl für
#                   Aliasse zugefügt
#

VERSION="1.2"

# ###########################################################
# Der Fenster-Rahmen für CallMonClient.
class CallMonClientFrame(wx.Frame):
  def __init__(self, pos, size, setup_data):
    style=wx.DEFAULT_FRAME_STYLE
    if FRAME_NO_TASKBAR==True:
      style|=wx.FRAME_NO_TASKBAR
    nam="CallMonClient v%s @ %s:%d"%(VERSION, setup_data[0], setup_data[1])
    wx.Frame.__init__(self, None, wx.ID_ANY, nam, pos=pos, size=size, style=style)
    if pos==wx.DefaultPosition:
      self.Centre()
    CallMonClient(self, setup_data)



# ###########################################################
# listmix.ColumnSorterMixin will das so....
class MyListCtrl(wx.ListCtrl):
  def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0):
    wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
    self.parent=parent



# ###########################################################
# Das eigentliche Fenster von CallMonClient.
class CallMonClient(wx.Panel, listmix.ColumnSorterMixin):
  def __init__(self, parent, setup_data):
    wx.Panel.__init__(self, parent, wx.ID_ANY, style=wx.WANTS_CHARS)

    self.parent=parent
    self.server_ip, self.server_socket, self.load_row_count, self.alias_dict, self.bg_color, self.oc_color, self.fg_color=setup_data
    self.msgtyp=MsgTyp()
    self.crypto=MiniCryptoV2()
    self.notification_queue=Queue()

    self.list_ctrl=MyListCtrl(self, style=wx.LC_REPORT|wx.BORDER_SUNKEN|wx.LC_SORT_ASCENDING)
    self.list_ctrl.SetBackgroundColour(self.bg_color)
    self.list_ctrl.SetTextColour(self.fg_color)

    r=wx.LIST_FORMAT_RIGHT
    l=wx.LIST_FORMAT_LEFT
    self.colHdrList =["Datum/Zeit", "Richtung", "NS#", "Nebenstelle Name", "Nummer (int)", "Nummer (ext)", "Name (ext)", "Dauer"]
    self.colPosList =[l,            l,          r,     l,                  l,              r,              l,            r      ]
    self.colLenList =[150,          70,         40,    150,                100,            100,            120,          70     ]

    cfgfl=CfgFile()
    colWidthList=cfgfl.getColWidth(self.colLenList)

    for i in range(len(self.colHdrList)):  # Spalten anlegen
      self.list_ctrl.InsertColumn(i, self.colHdrList[i], self.colPosList[i], width=colWidthList[i])
    listmix.ColumnSorterMixin.__init__(self, len(self.colHdrList))
    self.list_ctrl.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick)           # sortieren
    self.list_ctrl.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClick)  # Kontextmenü
    self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnDblClick)      # Doppelklick
    self.list_ctrl.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.OnFocused)         # links-Klick ("key-down")
    self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelected)       # links-Klick (quasi "key-up")
    self.deselected=None

    sizer=wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self.list_ctrl, 1, wx.EXPAND)
    self.SetSizer(sizer)
    sizer.Fit(self)
    self.list_ctrl.SetFocus()

    self.errMsg=u"Der CallMonServer auf %s:%d "%(self.server_ip, self.server_socket)

    self.connectToCallMonitorServerLost=False
    if self.server_ip=="":
      self.setupDialog(0)
      return
    else:
      self.connectToCallMonitorServer()
      if self.connectToCallMonitorServerLost==True:
        wx.MessageBox(self.errMsg+"antwortet nicht korrekt!", "Fehler", wx.OK|wx.ICON_ERROR)
        return

    self.popup=PopupControl(self)
    self.OWN_AREA_CODE=self.get_OWN_AREA_CODE()

    self.alias_dict_fixed=self.fixAreaCode(self.alias_dict)
    self.itemDataMap={}
    self.fillListCtrl()

    self.Bind(wx.EVT_TIMER, self.on_timer)  # self.notification_queue pollen
    self.timer=wx.Timer(self)
    self.updateIntervall=100                # 10 mal pro Sekunde sollte langen
    self.timer.Start(self.updateIntervall)

  # ###########################################################
  # Will listmix.ColumnSorterMixin so haben.
  def GetListCtrl(self):
   return(self.list_ctrl)
  def OnColClick(self, event):
    self.selectedItemDatas=self.getAllSelectedItemDatas() # ItemData der selektierten Zeilen merken
    wx.CallLater(10, self.reselectItemAfterSort)          # 10ms nach dem Sort die Selektierung wieder herstellen
    event.Skip()

  # ###########################################################
  # Setzt self.deselected auf den Index der selektierten Zeile,
  # sofern diese schon vorher als einzige Zeile selektiert war.
  def OnFocused(self, event):
    idx=event.GetIndex()    
    if self.list_ctrl.IsSelected(idx)==True and self.list_ctrl.GetSelectedItemCount()==1:
      self.deselected=idx

  # ###########################################################
  # De-Selektiert die selektierte Zeile, wenn ihr Index dem
  # Wert aus self.deselected entspricht. Dadurch wird (durch
  # die Brust ins Auge) erreicht, dass der erste Klick in eine
  # Zeile zu deren Selektierung führt und der zweite Klick in
  # dieselbe Zeile zur De-Selektierung.
  def OnSelected(self, event):
    idx=event.GetIndex()
    if idx==self.deselected:
      self.list_ctrl.Select(idx, 0)
    self.deselected=None

  # ###########################################################
  # Liefert eine Liste mit der ItemData von allen selektierten
  # Sätzen.
  def getAllSelectedItemDatas(self):
    idx=self.list_ctrl.GetFirstSelected()
    lst=[]
    while idx>=0:
      lst.append(self.list_ctrl.GetItem(idx, 0).GetData())
      idx=self.list_ctrl.GetNextSelected(idx)
    return(lst)

  # ###########################################################
  # Selektiert alle die Sätze, deren ItemData in der Liste
  # self.selectedItemDatas vorkommt.
  def reselectItemAfterSort(self):
    for itemData in self.selectedItemDatas:
      item=self.list_ctrl.FindItemData(0, itemData)
      self.list_ctrl.Select(item)

  # ###########################################################
  # Öffnet bei Doppelklick ein neues Fenster, in dem die
  # letzten 100 Telefonate mit der externen Telefonnummer aus
  # der geklickten Zeile angezeigt werden.
  def OnDblClick(self, event):
    idx=event.GetIndex()
    nr=self.list_ctrl.GetItem(idx, 5).GetText()
    rows=self.getRowsForNumber(nr)
    dlg=HistoryDialog(self, rows, (self.bg_color, self.fg_color)).Show()

  # ###########################################################
  # Verbindet sich mit dem CallMonitor-Server und startet bei
  # Erfolg notificationSocket() als Thread.
  def connectToCallMonitorServer(self):
    self.clientSock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.clientSock.settimeout(3)
    try:
      self.clientSock.connect((self.server_ip, self.server_socket))
    except Exception, e:
      self.clientSock=None
      print "Error: %s"%(str(e))
      return
    clientname="%s:%d"%self.clientSock.getsockname()  # eindeutigen Namen bauen
    try:
      self.clientSock.send("IamTheControlSocket,"+clientname)
      rc=self.clientSock.recv(1024)  # soll liefern:   OK,publicKey
    except:
      rc=""
    if rc[:2]!="OK":
      self.connectToCallMonitorServerLost=True
      return
    dummy, publicKey=rc.split(",", 1)
    self.crypto.setPublicKey(publicKey)

    self.notifySock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      self.notifySock.connect((self.server_ip, self.server_socket))
    except Exception, e:
      self.notifySock=None
      print "Error: %s"%(str(e))
      return
    try:
      self.notifySock.send("IamTheNotificationSocket,"+clientname)
      rc=self.notifySock.recv(128)  # soll liefern:   OK,-
    except:
      rc=""
    if rc[:2]!="OK":
      self.connectToCallMonitorServerLost=True
      return
    self.connectedNotificationSockets=[self.notifySock]

    worker1=threading.Thread(target=self.notificationSocket, name="notificationSocket")
    worker1.setDaemon(True)
    worker1.start()

  # ###########################################################
  # Läuft als Thread und wartet auf Notifications vom
  # CallMon-Server, um diese dann auf die Queue zu schreiben.
  def notificationSocket(self):
    while True:
      (rlist, wlist, xlist)=select.select(self.connectedNotificationSockets, [], [])

      for sock in rlist:
        try:
          strg=sock.recv(256)
        except:
          strg=""

        if strg=="":
          self.connectToCallMonitorServerLost=True
          return
        else:
          strg=strg.strip()
          print strg
          self.notification_queue.put(strg)

  # ###########################################################
  # Wird über wx.Timer zyklisch aufgerufen und fragt die Queue
  # ab. Wenn sich eine Notification auf der Queue befand, wird
  # das ListCtrl teilweise oder komplett neu befüllt.
  # Weiterhin wird ein Popup-Fenster mit den Daten zur Meldung
  # ausgegeben.
  def on_timer(self, event):
    self.checkForErrors() # Beendet ggf. nach Popup-Meldung das Programm

    if self.notification_queue.empty()==True: # wenn nix anliegt...fertig
      return

    self.timer.Stop()
    msgtxt=self.notification_queue.get()
    #NOTIFY,07.12.14 16:03:21;RING;0;0171xxxxxx9;0463xxxxxx7;SIP1;
    #NOTIFY,07.12.14 16:03:23;DISCONNECT;0;0;

    rs=msgtxt.split(";")
    if len(rs)>3:   # die conid aus der Meldung herausdröseln, um anhand dieser den zugehörigen Satz...
      conid=rs[2]   # ...in self.itemDataMap finden zu können.
    else:
      conid=None

    job=0     # 0=nix, 1="msg" anzeigen, 2=offene Verbindungen neu laden, 4=alle Verbindungen neu laden, 8="txt" anzeigen
    txt=u""

    if msgtxt.find(";RING;")>0:
      job=3
      txt=u"meldet einen ankommenden Telefonanruf!"
    elif msgtxt.find(";CALL;")>0:
      job=3
      txt=u"meldet einen ausgehenden Telefonanruf!"
    elif msgtxt.find(";CONNECT;")>0:
      job=3
      txt=u"meldet das Zustandekommen eines Gespräches!"
    elif msgtxt.find(";DISCONNECT;")>0:
      job=5
      txt=u"meldet eine beendete Verbindung!"
    elif msgtxt.find("NOTIFY,REFRESH")>=0:
      job=4
    elif msgtxt.find("NOTIFY,CONNECTION_LOST")>=0:
      job=8
      txt=self.errMsg+u"hat die Verbindung zur Fritzbox verloren!"
    else:
      print "Illegale Nachricht vom CallMonitor der Fritzbox empfangen"

    itemDataMapOpenBefore=self.getConidData(conid)  # offener Satz zur conid vor ListCtrl-Update

    if (job&2)==2:
      self.removeUnfinishedFromListCtrl() # alle derzeit angezeigten unbeendeten Verbindungen löschen
      self.updateListCtrlFromLog()        # alle unbeendeten Verbindungen vom CallMon-Server holen und anzeigen
      self.SortListItems(0, 0)

    if (job&4)==4:
      self.fillListCtrl()                 # komplett neu laden

    if (job&1)==1:
      #self.showTipWindow(self.errMsg+txt)
      itemDataMapOpenAfter=self.getConidData(conid) # offener Satz zur conid nach ListCtrl-Update
      msg=None
      if itemDataMapOpenBefore==None and itemDataMapOpenAfter!=None:    # vorher nix, nachher da -> CALL oder RING
        msg=CallMonitorMessage()
        msg.fromItemDataMap(itemDataMapOpenAfter)                       # den nachher-Satz laden
      elif itemDataMapOpenBefore!=None and itemDataMapOpenAfter!=None:  # vorher da, nachher da -> CONNECT
        msg=CallMonitorMessage()
        msg.fromItemDataMap(itemDataMapOpenAfter)                       # den nachher-Satz laden
      elif itemDataMapOpenBefore!=None and itemDataMapOpenAfter==None:  # vorher da, nachher nicht mehr -> DISCONNECT
        itemDataMapOpenAfter=self.getConidData(conid, itemDataMapOpenBefore[0]) # Satz zu conid + tmstmp(vorher) holen
        if itemDataMapOpenAfter==None:
          msg=None
        else:
          msg=CallMonitorMessage()
          msg.fromItemDataMap(itemDataMapOpenAfter)                     # den beendeten Satz laden

      if msg!=None:
        self.popup.showNew(msg)                                         # Satz zur Anzeige an Popup übergeben

    if (job&8)==8:
      self.popup.showNew(None, txt)   # den String "txt" direkt bzw. in Rohform als Popup anzeigen

    self.timer.Start(self.updateIntervall)

  # ###########################################################
  # Liefert zu einer "conid" deren Daten aus self.itemDataMap,
  # wenn der Satz als "offen" markiert ist.
  # Wird "tmstmp" mit !=None übergeben, muss auch dieser samt
  # "conid" zu den Daten passen - dafür muss der Satz als
  # "beendet" markiert sein.
  def getConidData(self, conid, tmstmp=None):
    for k, v in self.itemDataMap.items():
      if tmstmp==None and v[9]=="o" and v[8]==conid:    # kein tmstmp, offen und conid passt
        return(v)
      if tmstmp!=None and tmstmp==v[0] and v[9]=="f" and v[8]==conid: # tmstmp da und passt, finished und conid passt
        return(v)
    return(None)

  # ###########################################################
  # Zeigt eine Infomeldung mit aktueller Uhrzeit und "text" an.
  # Wird "noTime" mit True übergeben, wird nur "text" angezeigt.
  def showTipWindow(self, text, noTime=False):
    if noTime==True:
      strg=text
    else:
      strg="%s\n%s"%(time.strftime("%Y.%m.%d-%H:%M:%S"), text)
    tw=wx.TipWindow(self, strg, 400, wx.Rect(100, 100, 100, 100))

  # ###########################################################
  # Prüft auf Kommunikations-Fehler mit dem CallMonServer,
  # gibt ggf. ein entsprechendes Meldungs-Popup aus und
  # beendet danach das Programm.
  def checkForErrors(self):
    if self.connectToCallMonitorServerLost==True:
      wx.MessageBox(self.errMsg+"kommuniziert nicht mehr!", "Fehler", wx.OK|wx.ICON_ERROR)
      sys.exit()

    if self.clientSock==None:
      msg=self.errMsg+u"antwortet nicht!\nSoll der Setup-Dialog geöffnet werden?"
      rc=wx.MessageBox(msg, "Fehler", wx.YES_NO|wx.ICON_ERROR)
      if rc==wx.YES:
        self.setupDialog(0)
      sys.exit()

    if self.notifySock==None:
      wx.MessageBox(self.errMsg+"sendet nicht mehr!", "Fehler", wx.OK|wx.ICON_ERROR)
      sys.exit()

  # ###########################################################
  # Fragt die letzten "cnt" beendeten Telefonate beim
  # CallMonitor-Server an und liefert diese als Liste.
  def getRowsFromLogFinished(self, cnt):
    try:
      self.clientSock.send("GET_FINISHED_CALLS,%s"%(str(cnt)))
      bufLen=int(self.clientSock.recv(8))     # zu empfangende Byte lesen
      rows_str=""                             # Buffer initialisieren
      while len(rows_str)<bufLen:             # solange nicht alles empfangen wurde
        rows_str+=self.clientSock.recv(1024)  # empfangen und Buffer zufügen
      rows=json.loads(rows_str)               # Buffer "entpacken"
    except Exception, e:
      print "getRowsFromLogFinished", e
      return([])
    return(rows)

  # ###########################################################
  # Fragt die offenen Telefonate beim CallMonitor-Server an
  # und liefert diese als Liste.
  def getRowsFromLog(self):
    try:
      self.clientSock.send("GET_OPEN_CALLS")
      bufLen=int(self.clientSock.recv(8))    
      rows_str=""
      while len(rows_str)<bufLen:
        rows_str+=self.clientSock.recv(1024)
      rows=json.loads(rows_str)
    except Exception, e:
      print "getRowsFromLog", e
      return([])
    return(rows)

  # ###########################################################
  # Fragt die letzten 100 beendeten Telefonate mit der Nummer
  # "number" beim CallMonitor-Server an und liefert diese als
  # Liste.
  def getRowsForNumber(self, number):
    try:
      self.clientSock.send("GET_CALLS_FOR,%s"%(number))
      bufLen=int(self.clientSock.recv(8))     # zu empfangende Byte lesen
      rows_str=""                             # Buffer initialisieren
      while len(rows_str)<bufLen:             # solange nicht alles empfangen wurde
        rows_str+=self.clientSock.recv(1024)  # empfangen und Buffer zufügen
      rows=json.loads(rows_str)               # Buffer "entpacken"
    except Exception, e:
      print "getRowsForNumber", e
      return([])
    return(rows)

  # ###########################################################
  # Füllt die beendeten und die offenen Telefonate ins
  # ListCtrl.
  def fillListCtrl(self):
    self.itemDataMap={}
    self.list_ctrl.DeleteAllItems()
    self.tempIdxVals=[] # Liste aus self.itemDataMap-Keys von offenen Telefonaten

    self.updateListCtrlFromLogFinished()
    self.updateListCtrlFromLog()
    self.SortListItems(0, 0)  # ColumnSorterMixin -> Sortierung nach Col0, descending

  # ###########################################################
  # Löscht offene Telefonate aus dem ListCtrl.
  def removeUnfinishedFromListCtrl(self):
    for idx in self.tempIdxVals:
      item=self.list_ctrl.FindItemData(-1, idx)
      self.list_ctrl.DeleteItem(item)
      del self.itemDataMap[idx]
    self.tempIdxVals=[]

  # ###########################################################
  # Beendete Telefonate laden und darstellen.
  def updateListCtrlFromLogFinished(self):
    if self.clientSock==None:
      return
    idx=self.list_ctrl.GetItemCount() # Key in self.itemDataMap und self.list_ctrl

    rows=self.getRowsFromLogFinished(self.load_row_count)
    # 0             1        2    3         4        5        6             7    8      9
    # tmstmp_start, typ_seq, tel, tel_name, num_int, num_ext, num_ext_name, dur, conid, tel_pb
    for rowidx in range(len(rows)-1, -1, -1):
      rt=list(rows[rowidx])  # nach Liste wandeln, um ggf. Werte ändern zu können
      rt=self.numberToLocalAlias(rt)

      # die letzten drei Elemente werden verwendet, um einen Satz einer NOTIFY-Meldung zuordnen zu können
      r=(rt[0], rt[1], rt[2], rt[3], rt[4], rt[5], rt[6], int(rt[7]), rt[8], "f", rt[9])
      # die Spalte "dur" nach Integer wandeln, um korrekt sortieren zu können
      self.itemDataMap.update({idx : r})

      if rt[7]=="0":
        rt[7]=u"---"
      else:
        rt[7]=self.sec2hms(rt[7])
      r=(rt[0], rt[1], rt[2], rt[3], rt[4], rt[5], rt[6], rt[7])
      self.insertRowInListCtrl(idx, r)
      idx+=1
    return(idx)

  # ###########################################################
  # Offene Telefonate laden und darstellen.
  # Die Index-Werte aller eingestellten Sätze werden in
  # self.tempIdxVals gespeichert.
  def updateListCtrlFromLog(self):
    if self.clientSock==None:
      return
    idx=self.list_ctrl.GetItemCount() # Key in self.itemDataMap und self.list_ctrl

    rows=self.getRowsFromLog()
    # 0       1    2    3         4        5        6             7    8      9
    # tmstmp, typ, tel, tel_name, num_int, num_ext, num_ext_name, "0", conid, tel_pb
    for rowidx in range(len(rows)-1, -1, -1):
      rt=list(rows[rowidx])
      rt=self.numberToLocalAlias(rt)
      # die letzten drei Elemente werden verwendet, um einen Satz einer NOTIFY-Meldung zuordnen zu können
      r=(rt[0], rt[1], rt[2], rt[3], rt[4], rt[5], rt[6], int(rt[7]), rt[8], "o", rt[9])
      self.itemDataMap.update({idx : r})

      if rt[1].find(self.msgtyp.connect)>=0:
        rt[7]=u"offen"
      else:
        rt[7]=u"???"
      r=(rt[0], rt[1], rt[2], rt[3], rt[4], rt[5], rt[6], rt[7])
      self.insertRowInListCtrl(idx, r)
      item=self.list_ctrl.GetItem(idx)
      item.SetBackgroundColour(self.oc_color)
      self.list_ctrl.SetItem(item)
      self.tempIdxVals.append(idx)
      idx+=1
    return(idx)

  # ###########################################################
  # Ersetzt Nummern ggf. durch Aliasse. Namen aus dem Fritzbox-
  # oder 11880-Telefonbuch werden überschrieben.
  def numberToLocalAlias(self, numbers):
    if numbers[4] in self.alias_dict_fixed:                     # 4=num_int
      numbers[4]=self.alias_dict_fixed[numbers[4]]
    #if numbers[6]=="" and numbers[5] in self.alias_dict_fixed:  # 5=num_ext, 6=num_ext_name (Fritzbox-Telefonbuch bevorzugen)
    if numbers[5] in self.alias_dict_fixed:                     # 5=num_ext, 6=num_ext_name (Alias bevorzugen)
      numbers[6]=self.alias_dict_fixed[numbers[5]]
    return(numbers)

  # ###########################################################
  # Fügt "cols" mit dem Index "idx" self.list_ctrl hinzu.
  def insertRowInListCtrl(self, idx, cols):
    self.list_ctrl.InsertStringItem(idx, cols[0])
    for c in range(1, len(cols)):
      self.list_ctrl.SetStringItem(idx, c, cols[c])
    self.list_ctrl.SetItemData(idx, idx)

  # ###########################################################
  # Fragt das Fritzbox-Passwort ab und fordert damit beim
  # CallMon-Server ein Neu-Einlesen des Telefonbuchs an.
  def readPhonebook(self, event):
    if self.connectToCallMonitorServerLost==True:
      return
    dlg=wx.PasswordEntryDialog(self, "Fritzbox Passwort:")
    if dlg.ShowModal()!=wx.ID_OK:
      dlg.Destroy()
      return
    pwd=dlg.GetValue()
    dlg.Destroy()

    try:
      self.clientSock.send("READ_PHONEBOOKS,%s"%(self.crypto.encrypt(pwd)))
      strg=self.clientSock.recv(128)
    except:
      strg=""
    if strg[:4]=="DONE":
      wx.MessageBox("Die Telefonbücher wurden neu eingelesen!", "Info", wx.OK|wx.ICON_INFORMATION)
    else:
      wx.MessageBox("Das Einlesen der Telefonbücher ist fehlgeschlagen!", "Fehler", wx.OK|wx.ICON_ERROR)

  # ###########################################################
  # Fragt die eigene Vorwahlnummer beim Server an und liefert
  # diese zurück.
  def get_OWN_AREA_CODE(self):
    try:
      self.clientSock.send("GET_OWN_AREA_CODE")
      strg=self.clientSock.recv(128)
    except:
      strg=""
    return(strg)

  # ###########################################################
  # Wandelt eine Anzahl von Sekunden nach h:m:s.
  def sec2hms(self, sec):
    sec=int(sec)
    h=sec//3600
    m=(sec-h*3600)//60
    s=(sec-h*3600)%60
    if h==0:
      return("%02d:%02d"%(m, s))
    return("%02d:%02d:%02d"%(h, m, s))

  # ###########################################################
  # Kontextmenü für "self.list_ctrl" anlegen und darstellen.
  def OnRightClick(self, event):
    self.menue=wx.Menu()
    self.submenue=wx.Menu()
    self.menue.Append(90, 'Nummer (ext) in die Zwischenablage')
    self.menue.Append(95, 'Nummer (ext) oder Name (ext) suchen')
    self.menue.AppendSeparator()
    self.menue.Append(150, 'Telefonbuch von Fritzbox einlesen')
    self.menue.AppendSeparator()
    self.menue.Append(100, 'Einstellungen')
    self.menue.AppendSubMenu(self.submenue, 'Spalten anzeigen/verbergen')
    self.menue.Append(110, 'Fensterdaten speichern')
    self.menue.AppendSeparator()
    self.menue.Append(200, 'Über CallMonClient')

    for i in range(len(self.colHdrList)):
      self.submenue.Append(300+i, self.colHdrList[i], "", True)
      self.Bind(wx.EVT_MENU, self.showOrHideCols, id=300+i)
      self.submenue.Check(300+i, not self.list_ctrl.GetColumnWidth(i)==0)

    self.Bind(wx.EVT_MENU, self.nr2clipboard,     id=90)
    self.Bind(wx.EVT_MENU, self.findNumberOrName, id=95)
    self.Bind(wx.EVT_MENU, self.setupDialog,      id=100)
    self.Bind(wx.EVT_MENU, self.saveWindowPos,    id=110)
    self.Bind(wx.EVT_MENU, self.readPhonebook,    id=150)
    self.Bind(wx.EVT_MENU, self.aboutDialog,      id=200)
    self.PopupMenu(self.menue)

  # ###########################################################
  # Fragt einen Suchbegriff ab, der dann in der Tabelle mit
  # den beendeten Telefonaten in den Spalten "Nummer (ext)"
  # und "Name (ext)" gesucht wird. Das Ergebnis wird im
  # History-Dialog angezeigt.
  def findNumberOrName(self, event):
    dlg=wx.TextEntryDialog(self, "Suche nach Nummer oder Name ( Wildcards=['_', '%'] ):")
    if dlg.ShowModal()!=wx.ID_OK:
      dlg.Destroy()
      return
    seachFor=dlg.GetValue()
    dlg.Destroy()

    try:
      self.clientSock.send("FIND_CALLS_FOR,%s"%(json.dumps(seachFor)))
      bufLen=int(self.clientSock.recv(8))     # zu empfangende Byte lesen
      rows_str=""                             # Buffer initialisieren
      while len(rows_str)<bufLen:             # solange nicht alles empfangen wurde
        rows_str+=self.clientSock.recv(1024)  # empfangen und Buffer zufügen
      rows=json.loads(rows_str)               # Buffer "entpacken"
    except Exception, e:
      print "getRowsForNumber", e
      return
    if len(rows)==0:
      wx.MessageBox(u"Zu dem Suchbegriff <%s> wurden keine passenden Sätze gefunden!"%(seachFor), "Info", wx.OK|wx.ICON_INFORMATION)
    else:
      dlg=HistoryDialog(self, rows, (self.bg_color, self.fg_color)).Show()

  # ###########################################################
  # Kopiert die externe Telefonnummer aus der selektierten
  # Zeile ins Clipboard und zeigt dies mit einem Popup-Text an.
  def nr2clipboard(self, event):
    if self.list_ctrl.GetSelectedItemCount()>1:
      self.showTipWindow(u"Es ist nicht genau eine Zeile selektiert!", noTime=True)
      return
    idx=self.list_ctrl.GetFirstSelected()
    nr=self.list_ctrl.GetItem(idx, 5).GetText()
    self.copyToClipboard(nr)
    self.showTipWindow(u"Die Nummer %s wurde in der Zwischenablage abgelegt."%(nr), noTime=True)

  # ###########################################################
  # Kopiert "text" ins Clipboard.
  def copyToClipboard(self, text):
    if wx.TheClipboard.Open():
      do=wx.TextDataObject()
      do.SetText(text)
      wx.TheClipboard.SetData(do)
      wx.TheClipboard.Close()
    else:
      wx.MessageBox(u"Die Zwischenablage kann nicht geöffnet werden!", "Fehler", wx.OK|wx.ICON_ERROR)

  # ###########################################################
  # Schaltet gemäß Menüauswahl Spalten aus self.list_ctrl
  # zwischen Default-Breite und Null-Breite um.
  def showOrHideCols(self, event):
    col=event.GetId()-300   # Nummer der umzuschaltenden Spalte
    if self.submenue.IsChecked(event.GetId())==True:
      self.list_ctrl.SetColumnWidth(col, self.colLenList[col])
    else:
      self.list_ctrl.SetColumnWidth(col, 0)

  # ###########################################################
  # Setup-Dialog darstellen.
  def setupDialog(self, event):
    dlg=SetupDialog(self)
    dlg.setData(( self.server_ip, 
                  self.server_socket, 
                  self.load_row_count, 
                  self.alias_dict,
                  self.bg_color,
                  self.oc_color,
                  self.fg_color))
    if dlg.ShowModal()!=wx.ID_OK:
      dlg.Destroy()
      return
    data=dlg.getData()
    dlg.Destroy()
    server_ip, server_socket, load_row_count, alias_dict, bg_color, oc_color, fg_color=data

    reload_list_ctrl=restart_client=oc_color_changed=False
    if server_ip!=self.server_ip or server_socket!=self.server_socket:
      restart_client=True       # IP-Adresse oder Socket vom Server geändert
    if load_row_count!=self.load_row_count or self.aliasDictCompare(alias_dict, self.alias_dict)!=True:
      reload_list_ctrl=True     # Inhaltsverändernde Parameter für self.list_ctrl wurden geändert
    if oc_color!=self.oc_color:
      oc_color_changed=True     # die Hintergrundfarbe für offene Verbindungen wurde geändert
      oc_color_merk=self.oc_color

    self.server_ip, self.server_socket, self.load_row_count, self.alias_dict, self.bg_color, self.oc_color, self.fg_color=data
    cfgfl=CfgFile()
    cfgfl.setSetupData(data)

    self.list_ctrl.SetBackgroundColour(self.bg_color)
    self.list_ctrl.SetTextColour(self.fg_color)

    self.alias_dict_fixed=self.fixAreaCode(self.alias_dict)

    if restart_client==True:
      wx.MessageBox("Der CallMonClient muss neu gestartet werden!", "Info", wx.OK|wx.ICON_INFORMATION)
      sys.exit()

    if reload_list_ctrl==True:
      self.fillListCtrl()         # geänderte Aliasse oder Satzanzahl im ListCtrl korrigieren
    else:                         # wenn nicht ohnehin neu geladen wird
      if oc_color_changed==True:  # und die Hintergrundfarbe für offene Verbindungen geändert wurde
        for i in range(self.list_ctrl.GetItemCount()):  # über alle Sätze im list_ctrl
          if self.list_ctrl.GetItemBackgroundColour(i).GetAsString(wx.C2S_HTML_SYNTAX)==oc_color_merk:
            # Satz steht auf der alten Hintergrundfarbe für offene Verbindungen
            item=self.list_ctrl.GetItem(i)
            item.SetBackgroundColour(self.oc_color)   # Farbe neu setzen
            self.list_ctrl.SetItem(item)

  # ###########################################################
  # Liefert True, wenn die Inhalte der beiden alias_dict's
  # identisch sind. Sonst False.
  def aliasDictCompare(self, d1, d2):
    if len(d1)!=len(d2):
      return(False)   # Anzahl Elemente unterschiedlich
    for k, v in d1.items():
      d2v=d2.get(k, None)
      if d2v==None:
        return(False) # Key(d1) nicht in d2
      if d2v!=v:
        return(False) # Value(d1[k]) unterschiedlich zu Value(d2[k])
    return(True)

  # ###########################################################
  # Speichert die aktuellen Fenster-Daten
  #   Position, Größe, Spaltenbreiten
  # im Config-File.
  def saveWindowPos(self, event):
    pos=self.parent.GetScreenPosition()
    size=self.parent.GetSizeTuple()
    lst=[]
    for i in range(self.list_ctrl.GetColumnCount()):
      lst.append(self.list_ctrl.GetColumnWidth(i))
    cfgfl=CfgFile()
    cfgfl.setWindowSize(pos, size)
    cfgfl.setColWidth(lst)

  # ###########################################################
  # About-Box darstellen.
  def aboutDialog(self, event):
    info=wx.AboutDialogInfo()
    info.SetName("CallMonitor")
    info.SetVersion(VERSION)
    info.SetCopyright("D.A.  (11.2014)")
    info.SetDescription("Ein Programm zur Speicherung und Anzeige von Verbindungsdaten zu " \
                        "Telefonaten, die über die Fritzbox geführt werden bzw. wurden.")
    info.SetLicence("""
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.""")
    info.AddDeveloper("Detlev Ahlgrimm")
    wx.AboutBox(info)

  # ###########################################################
  # Prüft für allen Telefonnummern in "alias_dict", ob sie nicht
  # mit einer 0 beginnen und fügt der Liste in diesem Fall die
  # Nummer nochmal mit vorangestellter Vorwahl zu.
  #
  # Beginnt die Telefonnummer in "alias_dict" mit der eigenen
  # Vorwahl, wird die Nummer nochmal ohne Vorwahl zugefügt.
  def fixAreaCode(self, alias_dict):
    if self.OWN_AREA_CODE=="":
      return(alias_dict)

    alias_dict_fixed={}
    for nr, nam in alias_dict.items():
      alias_dict_fixed.update({nr:nam})
      if nr[:1] in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):   # wenn Nummer nicht mit 0 beginnt (also ohne Vorwahl)...
        alias_dict_fixed.update({self.OWN_AREA_CODE+nr:nam})        # ...dann Nummer nochmal mit Vorwahl einfügen
      if nr[:len(self.OWN_AREA_CODE)]==self.OWN_AREA_CODE:          # wenn Nummer mit der eigenen Vorwahl beginnt...
        alias_dict_fixed.update({nr[len(self.OWN_AREA_CODE):]:nam}) # ...dann Nummer nochmal ohne Vorwahl einfügen
    return(alias_dict_fixed)


if __name__=='__main__':
  app=wx.App()
  cfgfl=CfgFile()
  pos, size=cfgfl.getWindowSize()
  data=cfgfl.getSetupData()
  del cfgfl

  frame=CallMonClientFrame(pos, size, data)
  frame.Show()
  app.MainLoop()

