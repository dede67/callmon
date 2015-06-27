#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import datetime
from Database import Database

# ###########################################################
# Setzt den ArgParser auf.
def setupArgParser():
  desc="Löscht alle beendeten Telefonate aus der Datenbank des CallMon-Servers,\n" \
       "die in dem spezifizierten Zeitbereich liegen."
  usage="%(prog)s [-h] [-b] -a ALTER | -j JAHR [-m MONAT]"
  epilog="Beispiele:\n" \
         " -a 90     : löscht alle Telefonate, die über 90 Tage zurückliegen\n" \
         " -j 2014   : löscht alle Telefonate aus dem Jahr 2014\n" \
         " -j 14     : löscht alle Telefonate aus dem Jahr 2014\n" \
         " -j14 -m10 : löscht alle Telefonate aus dem Oktober 2014\n "
  parser=argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                  description=desc, usage=usage, epilog=epilog)
  parser.add_argument("-b", "--batch", action="store_true",
                    help="direkt löschen - ohne Abfrage nach Anzeige der Anzahl zu löschender Sätze.")
  parser.add_argument("-a", dest="alter", type=int, nargs=1,
                    help="löscht alle Telefonate, die mehr als ALTER Tage alt sind.")
  parser.add_argument("-j", dest="jahr", type=int, nargs=1, 
                    help="löscht alle Telefonate, die in dem Jahr JAHR geführt wurden.")
  parser.add_argument("-m", dest="monat", type=int, nargs=1, 
                    help="löscht alle Telefonate, die in dem Monat MONAT geführt wurden.")
  args=parser.parse_args()

  if args.alter==None and args.jahr==None and args.monat==None:
    parser.print_help()
    parser.error("entweder muss ALTER oder JAHR +[MONAT] übergeben werden!")
  if args.alter!=None and (args.jahr!=None or args.monat!=None):
    parser.error("ALTER darf nicht zusammen mit JAHR +[MONAT] übergeben werden!")
  if args.alter!=None and args.alter[0]<0:
    parser.error("ALTER darf nicht kleiner Null sein!")
  if args.jahr==None and args.monat!=None:
    parser.error("MONAT darf nur zusammen mit JAHR übergeben werden!")
  if args.jahr!=None and args.jahr[0]<0:
    parser.error("JAHR darf nicht kleiner Null sein!")
  if args.monat!=None and args.monat[0] not in range(1, 13):
    parser.error("MONAT muss zwischen 1 und 12 liegen!")
  return(args)



if __name__=='__main__':
  args=setupArgParser()
  db=Database()
  today=datetime.date.today().strftime("%Y.%m.%d")

  if args.alter!=None:
    deldate=(datetime.date.today()-datetime.timedelta(args.alter[0])).strftime("%Y-%m-%d")
    isRange=True
    print "Es werden alle Sätze gelöscht, deren Datum kleiner als", deldate, "ist."

  if args.jahr!=None:
    if args.jahr[0]<100:
      deldate=str(2000+args.jahr[0])
    else:
      deldate=str(args.jahr[0])
    if args.monat!=None:
      deldate+='-%02d'%(args.monat[0])
    isRange=False
    print "Es werden alle Sätze gelöscht, deren Datum mit", deldate, "beginnt."

  allcnt, cnt, dts, dte=db.prepareDelete(deldate, isRange)
  print
  print "Anzahl von Sätzen insgesamt          :", allcnt
  print "Davon auf das Löschkriterium passend :", cnt
  print "Zeitbereich der Sätze (jüngster Satz):", dts
  print "Zeitbereich der Sätze (ältester Satz):", dte
  print

  if cnt>0:
    if args.batch==False:
      print "Sollen die Sätze wirklich aus der Datenbank gelöscht werden?"
      ans=raw_input("Dann bitte  Ja  eingeben: ")
    else:
      ans="Ja"

    if ans=="Ja":
      db.executeDelete(deldate, isRange)
      print "Die Sätze wurden gelöscht!"
    else:
      print "Abgebrochen...."
  else:
    print "Nichts zu tun..."


