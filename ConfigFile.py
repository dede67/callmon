#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import wx

CFGFILE=os.path.join(os.path.expanduser('~'), ".CallMonClient.conf")


class CfgFile():
  def __init__(self):
    self.fc=wx.FileConfig(localFilename=CFGFILE)

  # ###########################################################
  # Fenster-Größe und -Position lesen/schreiben.
  def getWindowSize(self):
    posx=self.fc.ReadInt("pos_x", -1)
    posy=self.fc.ReadInt("pos_y", -1)
    sizex=self.fc.ReadInt("size_x", 820)
    sizey=self.fc.ReadInt("size_y", 200)
    pos=(posx, posy)    # (-1, -1) entspricht wx.DefaultPosition
    size=(sizex, sizey) # (-1, -1) entspricht wx.DefaultSize
    return((pos, size))
  # -----------------------------------------------------------
  def setWindowSize(self, pos, size):
    self.fc.WriteInt("pos_x",    pos[0])
    self.fc.WriteInt("pos_y",    pos[1])
    self.fc.WriteInt("size_x" ,  size[0])
    self.fc.WriteInt("size_y" ,  size[1])
    self.fc.Flush()

  # ###########################################################
  # Spalten-Breiten des ListCtrls lesen/schreiben.
  def getColWidth(self, colDefaultLenList):
    lst=[]
    for v in range(len(colDefaultLenList)):
      lst.append(self.fc.ReadInt("COLWIDTH.%d"%(v), colDefaultLenList[v]))
    return(lst)
  # -----------------------------------------------------------
  def setColWidth(self, colList):
    for c in range(len(colList)):
      self.fc.WriteInt("COLWIDTH.%d"%(c), colList[c])
    self.fc.Flush()

  # ###########################################################
  # Setup-Dialog-Daten lesen/schreiben.
  def getSetupData(self):
    host=self.fc.Read("server_ip",           "")
    socket=self.fc.ReadInt("server_socket",  26260)
    rowCnt=self.fc.ReadInt("load_row_count", 42)
    aliasCnt=self.fc.ReadInt("alias_count",  0)
    rows={}
    for r in range(aliasCnt):
      telnr=self.fc.Read("alias_telnr.%d"%(r), "")
      alias=self.fc.Read("alias_alias.%d"%(r), "")
      rows.update({telnr:alias})
    bg_color=self.fc.Read("bg_color", "#FFFFFF")
    oc_color=self.fc.Read("oc_color", "#BFD8FF")
    fg_color=self.fc.Read("fg_color", "#000000")
    return((host, socket, rowCnt, rows, bg_color, oc_color, fg_color))
  # -----------------------------------------------------------
  def setSetupData(self, data):
    host, socket, rowCnt, rows, bg_color, oc_color, fg_color=data
    self.fc.Write("server_ip",         host)
    self.fc.WriteInt("server_socket",  socket)
    self.fc.WriteInt("load_row_count", rowCnt)
    self.fc.WriteInt("alias_count",    len(rows))
    i=0
    for k, v in rows.items():
      self.fc.Write("alias_telnr.%d"%(i), k)
      self.fc.Write("alias_alias.%d"%(i), v)
      i+=1
    self.fc.Write("bg_color", str(bg_color))
    self.fc.Write("oc_color", str(oc_color))
    self.fc.Write("fg_color", str(fg_color))
    self.fc.Flush()


