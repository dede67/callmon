#!/usr/bin/env python
# -*- coding: utf-8 -*-

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from base64 import b64decode

# ###########################################################
# Ersatz für MiniCrypto (V1) - nun mit private/public-Keys.
#
# Basierend auf:
# https://launchkey.com/docs/api/encryption/python/pycrypto#encrypt
class MiniCryptoV2():
  # ###########################################################
  # Durch die Angabe von "bits" beim Init wird die Klasse für
  # den Server (mit privateKey) angelegt.
  # Als Klasse für den Client muss der publicKey des Servers
  # nach Init mit setPassword() eingestellt werden.
  def __init__(self, bits=None):
    self.public_key=None
    self.private_key=None
    if bits!=None:
      self.__generate_RSA(bits)

  # ###########################################################
  # Liefert den öffentlichen Schlüssel.
  def getPublicKey(self):
    return(self.public_key)

  # ###########################################################
  # Stellt den öffentlichen Schlüssel für encrypt() ein.
  def setPublicKey(self, public_key):
    self.public_key=public_key

  # ###########################################################
  # Liefert die verschlüsselte Version des Strings "textu".
  def encrypt(self, textu):
    return(self.__encrypt_RSA(self.public_key, textu.encode("windows-1252")))

  # ###########################################################
  # Liefert die entschlüsselte Version von "textv".
  def decrypt(self, textv):
    try:
      msg=self.__decrypt_RSA(self.private_key, textv).decode("windows-1252")
    except Exception, e:
      return(None)
    return(msg)

  # ###########################################################
  # Erzeugt ein Schlüssel-Paar und liefert es als Tupel.
  def __generate_RSA(self, bits=2048):
    new_key=RSA.generate(bits, e=65537)
    self.public_key=new_key.publickey().exportKey("PEM")
    self.private_key=new_key.exportKey("PEM")
    return(self.private_key, self.public_key)

  # ###########################################################
  # Verschlüsselt "message" mit dem Schlüssel "public_key".
  def __encrypt_RSA(self, public_key, message):
    rsakey=RSA.importKey(public_key)
    rsakey=PKCS1_OAEP.new(rsakey)
    encrypted=rsakey.encrypt(message)
    return(encrypted.encode('base64'))

  # ###########################################################
  # Entschlüsselt "package" mit dem Schlüssel "private_key".
  def __decrypt_RSA(self, private_key, package):
    rsakey=RSA.importKey(private_key)
    rsakey=PKCS1_OAEP.new(rsakey)
    decrypted=rsakey.decrypt(b64decode(package))
    return(decrypted)


if __name__=='__main__':
  # Server
  mcs=MiniCryptoV2(1024)
  publ=mcs.getPublicKey()
  print "Öffentlicher Schlüssel:\n", publ, "\n"


  # Client
  mcc=MiniCryptoV2()
  mcc.setPublicKey(publ)
  msg=mcc.encrypt(u"bla blub Zatterkram äöü")
  print "Verschlüsselte Nachricht:\n", msg, "\n"

  # Server
  print "Entschlüsselte Nachricht:\n", mcs.decrypt(msg), "\n"

  mcs=MiniCryptoV2(1024)
  print "Nachricht bei falschem Key:\n", mcs.decrypt(msg), "\n"

