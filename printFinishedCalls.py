#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ###########################################################
# Ausgabe aller abgeschlossenen Telefonate als ASCII-Tabelle.
# D.A. 03.03.2015
# ###########################################################

import argparse
import codecs
import locale
import sys
from Database import Database

# ###########################################################
# Liefert die Länge (in Character) pro Spalte als Liste.
def getColWidth(row):
  cols=[]
  for col in range(len(row)): # über alle Tupel
    l=len(row[col])           # Länge bestimmen
    cols.append(l)            # merken
  return(cols)

# ###########################################################
# Liefert die jeweils maximale Länge (in Character) pro
# Spalte als Liste.
def findMaxColWidth(rows):
  retList=[]
  for row in rows:                # über alle Zeilen
    cols=getColWidth(row)         # Spalten-Breite der akt. Zeile bestimmen
    for idx in range(len(cols)):  # in Ergebnis-Liste einpflegen
      try:
        retList[idx]=max(retList[idx], cols[idx]) # den größeren Wert merken
      except IndexError:
        retList.append(cols[idx]) # Spalte noch nicht in Ergebnis-Liste enthalten
  return(retList)

# ###########################################################
# Setzt den ArgParser auf.
def setupArgParser():
  desc="Anzeige aller beendeten Telefonate aus der Datenbank des CallMon-Servers als ASCII-Tabelle."

  parser=argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=desc)
  parser.add_argument("-n", dest="count", type=int, nargs=1,
                    help="gibt nur die COUNT neuesten Telefonate aus.")
  args=parser.parse_args()
  return(args)




if __name__=='__main__':
  args=setupArgParser()

  # http://stackoverflow.com/a/4546129/3588613
  sys.stdout=codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

  db=Database()
  
  count=0   # 0 heisst "alle"
  if args.count!=None:
    count=args.count[0]
  rows=db.getRowsFromLogFinished(count)

  maxColWidth=findMaxColWidth(rows)

  # 0             1        2    3         4        5        6             7    8      9
  # tmstmp_start, typ_seq, tel, tel_name, num_int, num_ext, num_ext_name, dur, conid, tel_pb
  #                 0     1     2      3      4      5      6     7
  # formatStr=u'| %19s | %9s | %2s | %18s | %11s | %14s | %40s | %4s |'
  formatStr=u'|'
  for i in range(8):  # nur die ersten 8 Spalten anzeigen
    formatStr+=' %'+str(maxColWidth[i])+'s |'

  for row in rows:
    try:  # falls das Script z.B. mit "|head -n 20" aufgerufen wird - Fehlermeldung unterdrücken
      print formatStr%(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
    except:
      break


