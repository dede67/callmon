#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wx


# ###########################################################
# Ein Setup-Dialog-Fenster zum Einstellen von
#   CallMon-Server-IP + Socket
#   zu holender Zeilenanzahl beendeter Telefonate
#   einer Liste von Telefonnummer+Alias
class SetupDialog(wx.Dialog):
  def __init__(self, parent):
    wx.Dialog.__init__(self, parent, wx.ID_ANY, "Setup", style=wx.CAPTION|wx.CLOSE_BOX|wx.RESIZE_BORDER)
    self.parent=parent

    self.InitUI()
    self.Centre()

  # ###########################################################
  # Fenster-Inhalt definieren
  def InitUI(self):
    sizer=wx.GridBagSizer(4, 4)

    sb=wx.StaticBox(self, wx.ID_ANY, " CallMon-Server ")
    sbsizer=wx.StaticBoxSizer(sb, wx.VERTICAL)
    sbssizer=wx.GridBagSizer(4, 4)
    st=wx.RIGHT
    sl=wx.LEFT|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT

    txt1=wx.StaticText(self, label="IP-Adresse oder Hostname:")
    self.callMonServerIP=wx.TextCtrl(self, wx.ID_ANY, "", size=(220, -1))
    sbssizer.Add(txt1,                     (0, 0), (1, 1), sl, 4)
    sbssizer.Add(self.callMonServerIP,     (0, 1), (1, 1), st, 4)

    txt2=wx.StaticText(self, label="Socketnummer:")
    self.callMonServerSocket=wx.SpinCtrl(self, min=0, max=65535, size=(80, -1))
    sbssizer.Add(txt2,                     (1, 0), (1, 1), sl, 4)
    sbssizer.Add(self.callMonServerSocket, (1, 1), (1, 1), st, 4)
    sbsizer.Add(sbssizer,  0, wx.ALL, 5)

    txt3=wx.StaticText(self, label="Anzahl zu ladender beendeter Telefonate:")
    self.loadRowCount=wx.SpinCtrl(self, min=0, max=99, size=(50, -1))
    self.loadRowCount.SetValue(42)

    self.alias=wx.ListCtrl(self, size=(300, 150), style=wx.LC_REPORT)
    self.alias.InsertColumn(0, "Telefonnummer", width=170)
    self.alias.InsertColumn(1, "Alias", width=100)

    add=wx.Button(self, wx.ID_ANY, "&neu")
    rem=wx.Button(self, wx.ID_ANY, "&löschen")
    add.Bind(wx.EVT_BUTTON, self.addBut)
    rem.Bind(wx.EVT_BUTTON, self.remBut)    

    txt4=wx.StaticText(self, label="Hintergrundfarbe:")
    self.bg_color=wx.ColourPickerCtrl(self, wx.ID_ANY)
    txt5=wx.StaticText(self, label="Hintergrundfarbe (offene Verbindung):")
    self.oc_color=wx.ColourPickerCtrl(self, wx.ID_ANY)
    txt6=wx.StaticText(self, label="Schriftfarbe:")
    self.fg_color=wx.ColourPickerCtrl(self, wx.ID_ANY)

    sizer.Add(sbsizer,                  (0, 0), (1, 3), wx.LEFT|wx.TOP|wx.RIGHT, 4)
    sizer.Add(txt3,                     (1, 0), (1, 1), sl, 4)
    sizer.Add(self.loadRowCount,        (1, 1), (1, 1), wx.LEFT|wx.TOP|wx.BOTTOM|wx.ALIGN_RIGHT, 4)
    sizer.Add(self.alias,               (2, 0), (4, 2), wx.LEFT|wx.BOTTOM|wx.EXPAND, 4)
    sizer.Add(add,                      (3, 2), (1, 1), st|wx.ALIGN_RIGHT, 4)
    sizer.Add(rem,                      (4, 2), (1, 1), st|wx.ALIGN_RIGHT, 4)
    sizer.AddGrowableRow(2, 0)
    sizer.AddGrowableCol(0, 0)

    sizer.Add(txt4,           (6, 0), (1, 1), sl, 4)
    sizer.Add(self.bg_color,  (6, 1), (1, 1), sl, 4)
    sizer.Add(txt5,           (7, 0), (1, 1), sl, 4)
    sizer.Add(self.oc_color,  (7, 1), (1, 1), sl, 4)
    sizer.Add(txt6,           (8, 0), (1, 1), sl, 4)
    sizer.Add(self.fg_color,  (8, 1), (1, 1), sl, 4)

    ok=wx.Button(self, wx.ID_OK, "&Ok")
    cancel=wx.Button(self, wx.ID_CANCEL, "&Cancel")
    ok.Bind(wx.EVT_BUTTON, self.okBut)
    cancel.Bind(wx.EVT_BUTTON, self.cancelBut)    

    h2sizer=wx.BoxSizer(wx.HORIZONTAL)
    h2sizer.Add(ok,      0, wx.RIGHT, 4)
    h2sizer.Add(cancel,  0, wx.LEFT, 4)
    sizer.Add(h2sizer, (9, 0), (1, 3), wx.ALIGN_RIGHT|wx.TOP|wx.BOTTOM|wx.RIGHT, 4)

    self.SetSizer(sizer)
    sizer.Fit(self)
    ok.SetFocus()

  # ###########################################################
  # Stellt die Defaultwerte in den Controls gemäß "data" ein.
  def setData(self, data):
    host, socket, count, rows, bg_color, oc_color, fg_color=data
    self.callMonServerIP.SetValue(host)
    self.callMonServerSocket.SetValue(socket)
    self.loadRowCount.SetValue(count)
    for k, v in rows.items():
      i=self.alias.InsertStringItem(0, k)
      self.alias.SetStringItem(i, 1, v)
    self.bg_color.SetColour(bg_color)
    self.oc_color.SetColour(oc_color)
    self.fg_color.SetColour(fg_color)

  # ###########################################################
  # neu-Button wurde gewählt.
  def addBut(self, event):
    dlg=AliasDialog(self)
    if dlg.ShowModal()!=wx.ID_OK:
      dlg.Destroy()
      return
    tel, alias=dlg.getData()
    dlg.Destroy()
    if tel=="" or alias=="":
      return

    i=self.alias.InsertStringItem(0, tel)
    self.alias.SetStringItem(i, 1, alias)
    self.alias.SetItemData(i, 0)

  # ###########################################################
  # löschen-Button wurde gewählt.
  def remBut(self, event):
    it=self.alias.GetFirstSelected()
    while it>-1: # solange mind. ein Satz selektiert ist
      name=self.alias.GetItem(it, 0).GetText()
      self.alias.DeleteItem(it)
      it=self.alias.GetFirstSelected()

  # ###########################################################
  # Ok-Button wurde gewählt.
  def okBut(self, event):
    self.EndModal(wx.ID_OK)

  # ###########################################################
  # Cancel-Button wurde gewählt.
  def cancelBut(self, event):
    self.EndModal(wx.ID_CANCEL)

  # ###########################################################
  # Liefert die Daten des Dialoges.
  def getData(self):
    rows={}
    cnt=self.alias.GetItemCount()
    for r in range(cnt):
      telnr=self.alias.GetItem(r, 0).GetText()
      alias=self.alias.GetItem(r, 1).GetText()
      rows.update({telnr:alias})
    return((self.callMonServerIP.GetValue(), 
            self.callMonServerSocket.GetValue(),
            self.loadRowCount.GetValue(),
            rows,
            self.bg_color.GetColour().GetAsString(wx.C2S_HTML_SYNTAX),
            self.oc_color.GetColour().GetAsString(wx.C2S_HTML_SYNTAX),
            self.fg_color.GetColour().GetAsString(wx.C2S_HTML_SYNTAX) ))



# ###########################################################
# Ein kleines Dialog-Fenster zum Einstellen von Telefonnummer
# und Alias.
class AliasDialog(wx.Dialog):
  def __init__(self, parent):
    wx.Dialog.__init__(self, parent, wx.ID_ANY, "Alias anlegen", style=wx.CAPTION|wx.CLOSE_BOX|wx.RESIZE_BORDER)
    self.parent=parent

    self.InitUI()
    self.Centre()

  # ###########################################################
  # Fenster-Inhalt definieren
  def InitUI(self):
    sizer=wx.GridBagSizer(4, 4)

    txt1=wx.StaticText(self, label="Telefonnummer:")
    self.tel=wx.TextCtrl(self, wx.ID_ANY, "", size=(170, -1))

    txt2=wx.StaticText(self, label="Alias:")
    self.alias=wx.TextCtrl(self, wx.ID_ANY, "", size=(100, -1))

    sizer.Add(txt1,                  (0, 0), (1, 1), wx.LEFT|wx.TOP, 4)
    sizer.Add(txt2,                  (0, 1), (1, 1), wx.LEFT|wx.TOP, 4)
    sizer.Add(self.tel,              (1, 0), (1, 1), wx.LEFT|wx.EXPAND, 4)
    sizer.Add(self.alias,            (1, 1), (1, 1), wx.LEFT|wx.RIGHT|wx.EXPAND, 4)
    sizer.AddGrowableCol(0, 0)
    sizer.AddGrowableCol(1, 0)

    ok=wx.Button(self, wx.ID_OK, "&Ok")
    cancel=wx.Button(self, wx.ID_CANCEL, "&Cancel")
    ok.Bind(wx.EVT_BUTTON, self.okBut)
    cancel.Bind(wx.EVT_BUTTON, self.cancelBut)    

    sizer.Add(ok,         (2, 0), (1, 1), wx.ALIGN_RIGHT|wx.BOTTOM, 4)
    sizer.Add(cancel,     (2, 1), (1, 1), wx.LEFT|wx.ALIGN_RIGHT|wx.RIGHT|wx.BOTTOM, 4)

    self.SetSizer(sizer)
    sizer.Fit(self)
    self.tel.SetFocus()

  # ###########################################################
  # Ok-Button wurde gewählt.
  def okBut(self, event):
    self.EndModal(wx.ID_OK)

  # ###########################################################
  # Cancel-Button wurde gewählt.
  def cancelBut(self, event):
    self.EndModal(wx.ID_CANCEL)

  # ###########################################################
  # Liefert Telefonnummer und Alias als Tupel aus zwei Strings.
  def getData(self):
    return((self.tel.GetValue(), self.alias.GetValue()))

