#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wx
import wx.lib.mixins.listctrl as listmix

# ###########################################################
# listmix.ColumnSorterMixin will das so....
class MyListCtrl(wx.ListCtrl):
  def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0):
    wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
    self.parent=parent


# ###########################################################
# Ein "quick and dirty" (per copy&paste) entstandener Dialog
# zur Anzeige von Gesprächs-Daten.
class HistoryDialog(wx.Dialog, listmix.ColumnSorterMixin):
  def __init__(self, parent, rows, colors):
    wx.Dialog.__init__(self, parent, wx.ID_ANY, "Gesprächshistorie", size=(820, 400), style=wx.CAPTION|wx.CLOSE_BOX|wx.RESIZE_BORDER)
    self.parent=parent
    self.rows=rows
    self.bg_color, self.fg_color=colors

    self.InitUI()
    self.Centre()

  # ###########################################################
  # Fenster-Inhalt definieren
  def InitUI(self):
    self.list_ctrl=MyListCtrl(self, style=wx.LC_REPORT|wx.BORDER_SUNKEN|wx.LC_SORT_ASCENDING)

    r=wx.LIST_FORMAT_RIGHT
    l=wx.LIST_FORMAT_LEFT
    self.colHdrList =["Datum/Zeit", "Richtung", "NS#", "Nebenstelle Name", "Nummer (int)", "Nummer (ext)", "Name (ext)", "Dauer"]
    self.colPosList =[l,            l,          r,     l,                  l,              r,              l,            r      ]
    self.colLenList =[150,          70,         40,    150,                100,            100,            120,          70     ]

    for i in range(len(self.colHdrList)):  # Spalten anlegen
      self.list_ctrl.InsertColumn(i, self.colHdrList[i], self.colPosList[i], width=self.colLenList[i])
    listmix.ColumnSorterMixin.__init__(self, len(self.colHdrList))
    self.list_ctrl.Bind(wx.EVT_LIST_COL_CLICK, self.OnColClick)

    self.list_ctrl.SetBackgroundColour(self.bg_color)
    self.list_ctrl.SetTextColour(self.fg_color)
    self.fillListCtrl(self.rows)

    txt1=wx.StaticText(self, label="Anzahl angezeigter Gespräche:")
    anz=wx.TextCtrl(self, wx.ID_ANY, "", size=(50, -1), style=wx.TE_READONLY)
    anz.SetValue(str(len(self.rows)))

    ok=wx.Button(self, wx.ID_OK, "&Ok")
    ok.Bind(wx.EVT_BUTTON, self.okBut)

    sizer=wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self.list_ctrl, 1, wx.EXPAND)

    hsizer=wx.BoxSizer(wx.HORIZONTAL)
    hsizer.Add(txt1, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 4)
    hsizer.Add(anz, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 4)
    hsizer.Add(ok, 0, wx.ALL|wx.ALIGN_RIGHT, 4)

    sizer.Add(hsizer, 0, wx.ALL|wx.ALIGN_RIGHT)
    self.SetSizer(sizer)
    self.list_ctrl.SetFocus()

  # ###########################################################
  # Will listmix.ColumnSorterMixin so haben.
  def GetListCtrl(self):
   return(self.list_ctrl)
  def OnColClick(self, event):
    event.Skip()

  # ###########################################################
  # Ok-Button wurde gewählt.
  def okBut(self, event):
    self.Destroy()

  # ###########################################################
  # Füllt die [beendeten] Telefonate ins ListCtrl.
  def fillListCtrl(self, rows):
    self.itemDataMap={}

    idx=0
    # 0             1        2    3         4        5        6             7
    # tmstmp_start, typ_seq, tel, tel_name, num_int, num_ext, num_ext_name, dur
    for rowidx in range(len(rows)-1, -1, -1):
      rt=list(rows[rowidx])  # nach Liste wandeln, um ggf. Werte ändern zu können

      r=(rt[0], rt[1], rt[2], rt[3], rt[4], rt[5], rt[6], int(rt[7]))
      # die Spalte "dur" nach Integer wandeln, um korrekt sortieren zu können
      self.itemDataMap.update({idx : r})

      if rt[7]=="0":
        rt[7]=u"---"
      else:
        rt[7]=self.sec2hms(rt[7])
      r=(rt[0], rt[1], rt[2], rt[3], rt[4], rt[5], rt[6], rt[7])
      self.insertRowInListCtrl(idx, r)
      idx+=1

    self.SortListItems(0, 0)  # ColumnSorterMixin -> Sortierung nach Col0, descending

  # ###########################################################
  # Fügt "cols" mit dem Index "idx" self.list_ctrl hinzu.
  def insertRowInListCtrl(self, idx, cols):
    self.list_ctrl.InsertStringItem(idx, cols[0])
    for c in range(1, len(cols)):
      self.list_ctrl.SetStringItem(idx, c, cols[c])
    self.list_ctrl.SetItemData(idx, idx)

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

