#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import requests   # python-requests-0.12.1-2.1.2.noarch
from requests.auth import HTTPDigestAuth

# ###########################################################
# Kommunikation mit der Fritzbox zur Abfrage der verfügbaren
# Telefonbuch-IDs und der Inhalte der Telefonbücher zur ID.
#
# Grundgerüst von:
# https://github.com/wrow/PytzBox/blob/master/PytzBox.py
class Phonebook():
  def __init__(self, password=False, host="fritz.box"):
    try:
      # Warnings wegen fehlender Zertifikatsprüfung der Fritzbox abschalten
      requests.packages.urllib3.disable_warnings()
    except:
      pass
    self.__password=password
    self.__host=host
    self.__user=""

    self.__url_contact=           'https://{host}:49443/upnp/control/x_contact'
    self.__action_phonebooklist=  'urn:dslforum-org:service:X_AVM-DE_OnTel:1#GetPhonebookList'
    self.__envelope_phonebooklist='<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '\
                                  's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'\
                                  '<s:Body><u:GetPhonebookList xmlns:u="urn:dslforum-org:service:X_AVM-DE_OnTel:1">'\
                                  '</u:GetPhonebookList></s:Body></s:Envelope>'
    self.__action_phonebook=      'urn:dslforum-org:service:X_AVM-DE_OnTel:1#GetPhonebook'
    self.__envelope_phonebook=    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '\
                                  's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'\
                                  '<s:Body><u:GetPhonebook xmlns:u="urn:dslforum-org:service:X_AVM-DE_OnTel:1">'\
                                  '<NewPhonebookId>{NewPhonebookId}</NewPhonebookId></u:GetPhonebook></s:Body></s:Envelope>'

  # ###########################################################
  # liefert aus "xml_str" den Teilstring, der zwischen
  #  <"arg"> und </"arg"> steht.
  def __get_argument(self, xml_str, arg):
    v="<"+arg+">"
    p1=xml_str.find(v)
    if p1>=0:
      p2=xml_str.find("</"+arg+">", p1)
      if p2>=0:
        return(xml_str[p1+len(v):p2])
    return(None)

  # ###########################################################
  # Liefert die IDs der Telefonbücher als Liste von Integers.
  def getPhonebookList(self):
    try:
      response=requests.post(self.__url_contact.format(host=self.__host),
                             auth=HTTPDigestAuth(self.__user, self.__password),
                             data=self.__envelope_phonebooklist,
                             headers={'Content-Type': 'text/xml; charset="utf-8"', 'SOAPACTION': self.__action_phonebooklist},
                             verify=False)
    except Exception, e:
      err=str(e)
    else:
      if response.status_code==200:
        ids=[]
        resp=self.__get_argument(response.content, "NewPhonebookList")
        if resp!=None:
          for id in resp.split(','):
            ids.append(int(id))
          return((False, list(set(ids))))
        err='No phonebooks found'
      else:
        err='Request failed with status code: %s' % response.status_code
    return((True, err))


  # ###########################################################
  # Liefert das Telefonbuch mit der ID "id" als xml-String.
  # Die "id" muss in der Fritzbox existieren.
  def getPhonebook(self, id=0):
    try:
      response=requests.post(self.__url_contact.format(host=self.__host),
                             auth=HTTPDigestAuth(self.__user, self.__password),
                             data=self.__envelope_phonebook.format(NewPhonebookId=id),
                             headers={'Content-Type': 'text/xml; charset="utf-8"', 'SOAPACTION': self.__action_phonebook},
                             verify=False)
    except Exception, e:
      err=str(e)
    else:
      if response.status_code==200:
        url=self.__get_argument(response.content, "NewPhonebookURL")
        try:
          response=requests.get(url)
        except Exception, e:
          err=str(e)
        else:
          return((False, response.content))
      else:
        err='Request failed with status code: %s' % response.status_code
    return((True, err))


if __name__=='__main__':
  with open("/home/dede/callmon/alt/pwd.txt", "r") as file:
    pwd=file.read().strip()

  box=Phonebook(pwd)
  err, pbl=box.getPhonebookList()
  print pbl

  for i in pbl:
    print "*"*40, i, "*"*40
    rc, data=box.getPhonebook(i)
    print data

