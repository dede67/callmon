#!/usr/bin/env python
# -*- coding: utf-8 -*-

import struct
import random
import hashlib
from Crypto.Cipher import AES
import base64

class MiniCrypto():
  # ###########################################################
  # Liefert ein zufälliges Passwort.
  def getPassword(self):
    return(base64.b64encode(self.__randomString(16)))

  # ###########################################################
  # Stellt das Passwort für encrypt() und decrypt() ein.
  def setPassword(self, password):
    self.key=hashlib.sha256(password.encode("windows-1252")).digest()

  # ###########################################################
  # Liefert die verschlüsselte Version des Strings "textu".
  def encrypt(self, textu):
    iv=self.__randomString(16)
    encryptor=AES.new(self.key, AES.MODE_ECB, iv)
    strg=self.__string16pack(textu.encode("windows-1252"))
    return(base64.b64encode(iv+encryptor.encrypt(strg)))

  # ###########################################################
  # Liefert die entschlüsselte Version von "textv".
  def decrypt(self, textv):
    c1=base64.b64decode(textv)
    iv=c1[:16]
    decryptor=AES.new(self.key, AES.MODE_ECB, iv)
    c2=c1[16:]
    try:
      c3=decryptor.decrypt(c2)
    except ValueError:
      return(None)

    c4=self.__string16unpack(c3)
    if c4!=None:
      c4=c4.decode("windows-1252")
    return(c4)

  # ###########################################################
  # Liefert einen String mit zufälligen Zeichen der
  # Länge "laenge".
  def __randomString(self, laenge):
    return(''.join(chr(random.randint(0, 0xFF)) for i in range(laenge)))

  # ###########################################################
  # Liefert soviele zufällige Zeichen, wie nötig sind, um
  # "text" damit zu einer ganzzahlig durch 16 teilbaren Länge
  # aufzufüllen.
  def __len16(self, text):
    if len(text)%16==0: return("")
    return(self.__randomString(16-len(text)%16))

  # ###########################################################
  # Liefert "text" mit vorangestellter Längen-Info und
  # aufgefüllt mit sovielen zufälligen Zeichen, um ganzzahlig
  # durch 16 teilbar zu sein.
  def __string16pack(self, text):
    r=struct.pack('<h', len(text))+text+"."
    return(r+self.__len16(r))    

  # ###########################################################
  # Liefert einen mit __string16pack() verpackten Text wieder
  # in Ursprungsform.
  def __string16unpack(self, text):
    l=struct.unpack('<h', text[:2])[0]
    if l<0 or text[l+2:l+3]!=".":
      return(None)
    return(text[2:l+2])


if __name__=='__main__':
  mc=MiniCrypto()
  pwd=mc.getPassword()
  print "Passwort        :", pwd
  mc.setPassword(pwd)
  for i in range(3):
    cmsg=mc.encrypt(u"dies ist die zu verschlüsselnde Nachricht")
    print "verschlüsselt(%d):"%(i), cmsg
    print "entschlüsselt(%d):"%(i), mc.decrypt(cmsg)

  mc.setPassword(u"anderes Passwort")
  print "Fehler          :", mc.decrypt(cmsg)

