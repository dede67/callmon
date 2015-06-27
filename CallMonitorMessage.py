#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ###########################################################
# Ein Datensatz für einen Meldungs-String vom Fritzbox
# Callmonitor.
class CallMonitorMessage():
  def __init__(self):
    self.tmstmp=""        # Zeitstempel
    self.tmstmp2=""       # Zeitstempel (ggf. Zeit der DISCONNECT-Meldung)
    self.typ=""           # Typ (RING, CALL, CONNECT, DISCONNECT) oder als MsgTyp
    self.conid=""         # ConnectionID
    self.tel=""           # Nebenstelle
    self.tel_pb=""        # Nebenstelle (wie im Telefonbuch mit **X davor)
    self.tel_name=""      # Name der Nebenstelle gemäß Telefonbuch
    self.num_int=""       # Genutzte Nummer
    self.num_ext=""       # An[ge]rufene externe Nummer
    self.num_ext_name=""  # Name zu num_ext gemäß Telefonbuch
    self.dur=""           # Gesprächsdauer [Sek]
    self.sip=""           # SIP
    self.finished=""      # Kennung, ob Satz bereits nach LogFinished übertragen (X) oder E für Error

  def asList(self):
    return([self.tmstmp, self.tmstmp2, self.typ, self.conid, self.tel, self.tel_pb, self.tel_name,
            self.num_int, self.num_ext, self.num_ext_name, self.dur, self.sip])

  def fromList(self, lst):
    self.tmstmp, self.tmstmp2, self.typ, self.conid, self.tel, self.tel_pb, self.tel_name, \
    self.num_int, self.num_ext, self.num_ext_name, self.dur, self.sip=lst

  def fromItemDataMap(self, idm):
    #  0                       1         2    3    4           5               6            7    8    9     10
    #u'2014-12-07 18:15:30', u'<- -X', u'', u'', u'B\xfcro', u'0171xxxxxx9', u'Papa Handy', 0, u'0', 'f', u'**612')
    # 0             1        2    3         4        5        6             7    8      9   10
    # tmstmp_start, typ_seq, tel, tel_name, num_int, num_ext, num_ext_name, dur, conid, "", tel_pb
    if idm==None:
      return
    self.tmstmp=idm[0]
    self.typ=idm[1]
    self.conid=idm[8]
    self.tel=idm[2]
    self.tel_pb=idm[10]
    self.tel_name=idm[3]
    self.num_int=idm[4]
    self.num_ext=idm[5]
    self.num_ext_name=idm[6]
    self.dur=idm[7]
    

  def debugPrint(self):
    #           tmstmp    typ  conid   tel_pb   num_int   num_ext_name
    #                tmstmp2       tel     tel_name  num_ext   dur sip finished
    lst_format="%17s %17s %10s %2s %2s %5s %19s %15s %15s %15s %5s %5s %1s"
    if self.typ=="RING":
      t="RING <-"
    elif self.typ=="CALL":
      t="CALL ->"
    else:
      t=self.typ

    rs=lst_format%(self.tmstmp, self.tmstmp2, t, self.conid, self.tel, self.tel_pb, self.tel_name, 
                    self.num_int, self.num_ext, self.num_ext_name, self.dur, self.sip, self.finished)
    return(rs)


