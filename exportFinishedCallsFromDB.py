#!/usr/bin/env python
# -*- coding: utf-8 -*-

# ###########################################################
# Ausgabe aller abgeschlossenen Telefonate in csv-Notation.
# ###########################################################
# Aufruf z.B.:  ./exportFinishedCallsFromDB.py >call_dump.csv
# ###########################################################

import codecs
import locale
import sys
from Database import Database

if __name__=='__main__':
  # http://stackoverflow.com/a/4546129/3588613
  sys.stdout=codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

  db=Database()
  rows=db.getRowsFromLogFinished(0)

  # 0             1        2    3         4        5        6             7
  # tmstmp_start, typ_seq, tel, tel_name, num_int, num_ext, num_ext_name, dur
  formatStr=u'"%s";"%s";"%s";"%s";"%s";"%s";"%s";"%s"'

  for row in rows:
    try:  # falls das Script z.B. mit "|head -n 20" aufgerufen wird - Fehlermeldung unterdrücken
      print formatStr%(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
    except:
      break

