#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from lxml import etree    # python-lxml-2.3.4-2.1.2.x86_64


class ParseXML_Phonebook():
  def __init__(self, xml):
    self.root=etree.fromstring(xml)

  # ###########################################################
  # Wandelt eine XML-Datei mit folgender Struktur
  #   <phonebook...>
  #     <contact>
  #       <person>
  #         <realName>{realname}</realName>
  #       </person>
  #       <uniqueid>{fb_uniqueid}</uniqueid>
  #       <telephony>
  #         <number...>{number}</number>
  #         <number...>{number}</number>
  #         [...]
  #       </telephony>
  #     </contact>
  #     <contact>
  #       [... s.o. ...]
  #     </contact>
  #   </phonebook>
  # in ein Dictionary folgender Stuktur
  #   { realname:(uniqueid, [number, ...]), ... }
  def get(self):
    fndBook=self.root.find("phonebook")                     # <phonebook> anfahren
    pb_dict={}
    if fndBook!=None:
      fndContact=fndBook.findall("contact")                 # alle <contact> anfahren
      if fndContact!=None:
        for person in range(len(fndContact)):
          fndPerson=fndContact[person].find("person")       # <person> anfahren
          if fndPerson==None:
            continue

          realname=fndPerson.find("realName")               # <realname> auslesen
          if realname==None:
            continue

          fndUniqueid=fndContact[person].find("uniqueid")   # <uniqueid> anfahren
          if fndUniqueid==None:
            continue
          fb_uniqueid=fndUniqueid.text                      # <uniqueid> auslesen
          try:
            fb_uniqueid=int(fb_uniqueid)                    # <uniqueid> nach Integer wandeln
          except:
            continue

          fndTelephony=fndContact[person].find("telephony") # <telephony> anfahren
          if fndTelephony==None:
            continue

          fndNumber=fndTelephony.findall("number")          # alle <number> auslesen
          numberLst=[]
          for number in range(len(fndNumber)):
            numberLst.append(fndNumber[number].text)

          pb_dict.update({realname.text : (fb_uniqueid, numberLst)})  # in Dictionary ablegen
    return(pb_dict)



if __name__=='__main__':
  with open("/home/dede/callmon/alt/pb0.txt", "r") as file:
    xml=file.read()

  pb_dict=ParseXML_Phonebook(xml).get()
  for k, v in pb_dict.items():
    print k, v

