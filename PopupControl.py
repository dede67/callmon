#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wx
import time

from Queue              import Queue
from CallMonitorMessage import CallMonitorMessage
from MsgTyp             import MsgTyp



# ###########################################################
# Verwaltet die Positionen mehrerer Popup-Fenster.
class PopupControl(wx.EvtHandler):
  def __init__(self, parent):
    wx.EvtHandler.__init__(self)
    self.parent=parent
    self.openPopups=[]

    self.destroyed_queue=Queue()
    self.Bind(wx.EVT_TIMER, self.__onTimer)
    self.timer=wx.Timer(self)
    self.updateIntervall=100  # 10 mal pro Sekunde sollte langen
    # timer wird gestartet, wenn das erste Popup offen ist

  # ###########################################################
  # Liefert die rechte untere Ecke des primären Bildschirms.
  def __findCorner(self):
    dsp=wx.Display(0)
    startx, starty, width, height=dsp.GetGeometry()
    xm=width
    startx, starty, width, height=dsp.GetClientArea()
    ym=starty+height
    return((xm, ym))

  # ###########################################################
  # Stellt ein Popup-Fenster dar und merkt sich dessen Position
  # und Abmessung, um ggf. ein folgendes Popup-Fenster darüber
  # darstellen zu können.
  # Die Übergabe von "text" mit !=None führt in PopupWin()
  # dazu, dass "msg" nicht berücksichtigt wird.
  def showNew(self, msg, text=None):
    self.timer.Stop()
    win=PopupWin(self.parent, self.destroyed_queue, msg, text)
    w, h=win.GetSize()
    x, y=self.__findCorner()

    found=False
    ho=0
    while len(self.openPopups)>0:   # über alle [vermeintlich] offenen Popups (von jung nach alt)
      wino, xo, yo, wo, ho=self.openPopups[len(self.openPopups)-1]  # Handle, Position und Größe vom Jüngsten laden
      try:
        wino.isAlive()        # testen, obs noch "lebt"
        found=True            # lebt offenbar -> oberhalb davon kommt das neue Popup hin
        break
      except:
        self.openPopups.pop() # Popup ist schon weg - Jüngstes aus Liste entfernen

    if found==True:
      y=yo-ho

    if (y-h)>0:                                 # nur wenn noch Platz auf dem Bildschirm ist
      win.Position((x, y), (-w, -h))            # Position einstellen
      win.Show(True)                            # darstellen
      self.openPopups.append((win, x, y, w, h)) # und merken
    self.timer.Start(self.updateIntervall)

  # ###########################################################
  # Prüft 10x pro Sekunde, ob sich ein Popup ins Nirvana
  # abgemeldet hat und verschiebt in diesem Fall alle höher
  # gelegenen Popups entsprechend weit nach unten.
  def __onTimer(self, event):
    if self.destroyed_queue.empty()==True: # wenn nix anliegt...fertig
      return
    self.timer.Stop()
    msg=self.destroyed_queue.get()

    deadIdx={}
    hsum=0
    for i in range(len(self.openPopups)): # von alt nach jung durchlaufen
      wino, x, y, w, h=self.openPopups[i] # Handle, Position und Größe laden
      try:
        wino.isAlive()  # testen, obs noch "lebt"
      except:
        hsum+=h   # Summe aller toten Popup-Höhen
        deadIdx.update({i:(y, hsum)})  # Index, Y-Position und Höhen-Summe von totem Popup merken

    startMove=False
    for i in range(len(self.openPopups)): # von alt nach jung durchlaufen
      if i in deadIdx:          # über alle toten Popups
        yd, hsum=deadIdx[i]     # Höhen-Summe holen
        startMove=True          # [frühestens] beim nächsten Index mit dem Verschieben beginnen
        continue                # für diesen gibts nix mehr zu tun
      if startMove==True:
        wino, x, y, w, h=self.openPopups[i]         # Handle, Position und Größe laden
        wino.Position((x, y+hsum), (-w, -h))        # korrigierte Position setzen
        self.openPopups[i]=(wino, x, y+hsum, w, h)  # geänderte Position zurückschreiben

    l=list(deadIdx.keys())
    l.sort(reverse=True)      # von jung nach alt löschen...
    for i in l:
      del self.openPopups[i]  # ...damit sich nur die Indices der bereits bearbeitenden Popups verschieben

    if len(self.openPopups)>0:  # nur wenn Popups offen sind, muss __onTimer() auch laufen
      self.timer.Start(self.updateIntervall)





# ###########################################################
# Stellt ein Popup-Fenster mit dem Inhalt von "msg" dar,
# sofern "text" mit None übergeben wurde. Bei "text" !=None
# wird "msg" ignoriert und nur "text" ausgegeben.
class PopupWin(wx.PopupWindow):
  def __init__(self, parent, destroyed_queue, msg, text=None):
    wx.PopupWindow.__init__(self, parent)
    self.destroyed_queue=destroyed_queue

    if text==None:
      self.msgtyp=MsgTyp()  # Kenner "->", "<-", "bla" und "-X" laden
      self.SetBackgroundColour("YELLOW")
      self.__layoutMsg(msg)
    else:
      self.SetBackgroundColour("INDIAN RED")
      self.__layoutText(text)

    self.Layout()
    wx.CallLater(60000, self.__onLeftUp)  # Selbstzerstörung nach einer Minute == Anzeigedauer

  # ###########################################################
  # Stellt "msg" gemäß Inhalt dar.
  #
  #   Richtung  | Überschrift                         | lokale Nummer           | externe Nummer
  #  -----------+-------------------------------------+-------------------------+--------------------------
  #   <-        | ankommendes Telefonat               | für <intNummer>         | von <extNummer> / <Name>
  #   ->        | ausgehendes Telefonat               | von <Nebenstelle>       | nach <extNummer> / <Name>
  #             |                                     |                         |
  #   <- bla    | angenommenes ankommendes Telefonat  | an <Nebenstelle>        | von <extNummer> / <Name>
  #   -> bla    | angenommenes ausgehendes Telefonat  | von <Nebenstelle>       | bei <extNummer> / <Name>
  #             |                                     |                         |
  #   -> bla -X | beendetes Telefonat (<dauer>)       | zwischen <Nebenstelle>  | und <extNummer> / <Name>
  #   <- bla -X | beendetes Telefonat (<dauer>)       | zwischen <Nebenstelle>  | und <extNummer> / <Name>
  #   <- -X     | verpasstes Telefonat                | für <intNummer>         | von <extNummer> / <Name>
  #   -> -X     | nicht zustande gekommenes Telefonat | von <Nebenstelle>       | nach <extNummer> / <Name>
  #
  def __layoutMsg(self, msg):
    msgFont=wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    hdrFont=wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    hdrFont.SetWeight(wx.FONTWEIGHT_BOLD)

    strg=txt1=txt2=""
    intnr =msg.num_int
    ns    =msg.tel_pb   + u" / " + msg.tel_name
    extnr =msg.num_ext  + u" / " + msg.num_ext_name

    if msg.typ.find(self.msgtyp.ring)>=0:       # wenn ANKOMMEND
      strg=u"ankommendes Telefonat"
      txt1=u"für "+intnr
      txt2=u"von "+extnr
    elif msg.typ.find(self.msgtyp.call)>=0:     # wenn AUSGEHEND
      strg=u"ausgehendes Telefonat"
      txt1=u"von "+ns
      txt2=u"nach "+extnr

    if msg.typ.find(self.msgtyp.connect)>=0:    # wenn ANGENOMMEN
      strg=u"angenommenes "+strg
      if msg.typ.find(self.msgtyp.ring)>=0:     # und ANKOMMEND
        txt1=u"an "+ns
        txt2=u"von "+extnr
      else:                                     # wenn AUSGEHEND und angenommen
        txt1=u"von "+ns
        txt2=u"bei "+extnr

    if msg.typ.find(self.msgtyp.disconnect)>=0: # wenn BEENDET
      if msg.typ.find(self.msgtyp.connect)>=0:  # und ANGENOMMEN wurde
        strg=u"beendetes Telefonat (%s)"%self.__sec2hms(msg.dur)
        txt1=u"zwischen "+ns
        txt2=u"und "+extnr
      else:                                     # wenn beendet und NICHT ANGENOMMEN
        if msg.typ.find(self.msgtyp.ring)>=0:   # und beendet ANKOMMEND nicht angenommen
          strg=u"verpasstes Telefonat"
          txt1=u"für "+intnr
          txt2=u"von "+extnr
        else:                                   # wenn beendet AUSGEHEND nicht angenommen
          strg=u"nicht zustande gekommenes Telefonat"
          txt1=u"von "+ns
          txt2=u"nach "+extnr

    hdr=wx.StaticText(self, wx.ID_ANY, strg)
    hdr.SetFont(hdrFont)
    msg1=wx.StaticText(self, wx.ID_ANY, txt1.replace("&", "&&"))
    msg1.SetFont(msgFont)
    msg2=wx.StaticText(self, wx.ID_ANY, txt2.replace("&", "&&"))
    msg2.SetFont(msgFont)

    topsizer=wx.BoxSizer(wx.VERTICAL)
    sb=wx.StaticBox(self, wx.ID_ANY, " CallMon ")
    sizer=wx.StaticBoxSizer(sb, wx.VERTICAL)
    sizer.Add(hdr,  0, wx.ALL|wx.ALIGN_CENTER, 4)
    sizer.Add(msg1, 0, wx.ALL|wx.ALIGN_CENTER, 4)
    sizer.Add(msg2, 0, wx.ALL|wx.ALIGN_CENTER, 4)
    topsizer.Add(sizer, 0, wx.FIXED_MINSIZE|wx.ALL, 4)

    self.SetSizer(topsizer)
    topsizer.Fit(self)

    self.Bind(wx.EVT_LEFT_UP, self.__onLeftUp)
    sb.Bind(  wx.EVT_LEFT_UP, self.__onLeftUp)
    hdr.Bind( wx.EVT_LEFT_UP, self.__onLeftUp)
    msg1.Bind(wx.EVT_LEFT_UP, self.__onLeftUp)
    msg2.Bind(wx.EVT_LEFT_UP, self.__onLeftUp)

  # ###########################################################
  # Stellt "text" in einem Popup-Fenster dar.
  def __layoutText(self, text):
    msgFont=wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    hdrFont=wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    hdrFont.SetWeight(wx.FONTWEIGHT_BOLD)

    hdr=wx.StaticText(self, wx.ID_ANY, text.replace("&", "&&"))
    hdr.SetFont(hdrFont)

    topsizer=wx.BoxSizer(wx.VERTICAL)
    sb=wx.StaticBox(self, wx.ID_ANY, " CallMon ")
    sizer=wx.StaticBoxSizer(sb, wx.VERTICAL)
    sizer.Add(hdr,  0, wx.ALL|wx.ALIGN_CENTER, 4)
    topsizer.Add(sizer, 0, wx.FIXED_MINSIZE|wx.ALL, 4)

    self.SetSizer(topsizer)
    topsizer.Fit(self)

    self.Bind(wx.EVT_LEFT_UP, self.__onLeftUp)
    sb.Bind(  wx.EVT_LEFT_UP, self.__onLeftUp)
    hdr.Bind( wx.EVT_LEFT_UP, self.__onLeftUp)

  # ###########################################################
  # Wandelt eine Anzahl von Sekunden nach h:m:s.
  def __sec2hms(self, sec):
    sec=int(sec)
    h=sec//3600
    m=(sec-h*3600)//60
    s=(sec-h*3600)%60
    if h==0:
      return("%02d:%02d"%(m, s))
    return("%02d:%02d:%02d"%(h, m, s))

  # ###########################################################
  # Schließt das Popup-Fenster.
  def __onLeftUp(self, evt=0):
    self.Show(False)
    self.destroyed_queue.put("bye")
    self.Destroy()

  # ###########################################################
  # Dummy zum testen, ob das Popup-Fenster noch existent oder
  # schon geschlossen ist.
  def isAlive(self):
    return(True)





# ###########################################################
# Test-Umgebung
class TestPanel(wx.Panel):
  def __init__(self, parent):
    wx.Panel.__init__(self, parent)
    self.parent=parent

    self.popup=PopupControl(self)

    self.cnt=0
    btn=wx.Button(self, label="Open Popup")
    btn.Bind(wx.EVT_BUTTON, self.onShowPopup)

    sizer=wx.BoxSizer()
    sizer.Add(btn,  0, wx.ALL, 4)
    self.SetSizer(sizer)
    sizer.Fit(self)

  # ###########################################################
  #
  def onShowPopup(self, event=0):
    self.cnt+=1
    msg=CallMonitorMessage()
    msg.tmstmp=u"2014-12-07 08:42:18"
    msg.typ=u"<-"
    msg.conid=u"1"
    msg.tel=u"0"
    msg.tel_pb=u"**1"
    msg.tel_name=u"Büro"
    msg.num_ext=u"04xxxxxxx1"
    msg.num_int=u"04xxxxxxxx6"
    msg.sip=u"SIP0"
    msg.num_ext_name=u"O&O xxxxxx"
    msg.dur=u"64"

    if self.cnt==1:
      self.popup.showNew(msg)

    msg.typ=u"<- bla"
    if self.cnt==2:
      self.popup.showNew(msg)
      #self.popup.showNew(msg)

    msg.typ=u"<- bla -X"
    if self.cnt==3:
      self.popup.showNew(msg)

    msg.typ=u"<- -X"
    msg.dur=""
    if self.cnt==4:
      self.popup.showNew(msg)
    msg.dur=u"64"

    msg.typ=u"->"
    if self.cnt==5:
      self.popup.showNew(msg)

    msg.typ=u"-> bla"
    if self.cnt==6:
      self.popup.showNew(msg)

    msg.typ=u"-> bla -X"
    if self.cnt==7:
      self.popup.showNew(msg)

    msg.typ=u"-> -X"
    msg.dur=u""
    if self.cnt==8:
      self.popup.showNew(msg)

    errMsg=u"Der CallMonServer auf 11w:26260 "
    txt=errMsg+u"hat die Verbindung zur Fritzbox verloren!"
    if self.cnt==9:
      self.popup.showNew(None, txt)
      self.cnt=0

# ###########################################################
#
class TestFrame(wx.Frame):
  def __init__(self):
    wx.Frame.__init__(self, None, title="Test Popup")
    panel=TestPanel(self)
    self.Show()



if __name__ == "__main__":
  app=wx.App(False)
  frame=TestFrame()
  app.MainLoop()

