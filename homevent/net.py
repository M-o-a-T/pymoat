# -*- coding: utf-8 -*-

##
##  Copyright © 2007-2008, Matthias Urlichs <matthias@urlichs.de>
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU General Public License as published by
##  the Free Software Foundation, either version 3 of the License, or
##  (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##  GNU General Public License (included; see the file LICENSE)
##  for more details.
##

"""\
This code implements the base for TCP clients and servers.

"""

from homevent.logging import log,log_exc,DEBUG,TRACE,INFO,WARN,ERROR
from homevent.statement import Statement, main_words, AttributedStatement
from homevent.check import Check,register_condition,unregister_condition
from homevent.context import Context
from homevent.event import Event
from homevent.run import simple_event
from homevent.base import Name
from homevent.collect import Collection,Collected

from twisted.internet import protocol,reactor,error
from twisted.protocols.basic import LineReceiver,_PauseableMixin

import os

class DisconnectedError(RuntimeError):
	def __init__(self,dev):
		self.dev = dev
	def __str__(self):
		return "Disconnected: %s" % (self.dev,)
	
class idErr(RuntimeError):
	def __init__(self,path):
		self.path = path

class TimedOut(idErr):
	def __str__(self):
		return "Timeout: No data at %s" % (self.path,)

class NetError(EnvironmentError):
	def __init__(self,typ):
		self.typ = typ
	def __str__(self):
		if self.typ < 0:
			try:
				from errno import errorcode
				return "NET_ERR: %d: %s" % (self.typ,errorcode[self.typ])
			except Exception:
				pass
		return "NET_ERR %s" % (self.typ,)

	def __repr__(self):
		return "NetError(%d)" % (self.typ,)

class NetReceiver(object,LineReceiver, _PauseableMixin):
	"""A receiver for the line protocol.
	"""

	delimiter = "\n"

	def lineReceived(self, line):
		"""Override this.
		"""
		self.loseConnection()
		raise ProgrammingError("You need to override NetReceiver.lineReceived")

	def connectionMade(self):
		super(NetReceiver,self).connectionMade()
		self.factory.haveConnection(self)

	def loseConnection(self):
		if self.transport:
			self.transport.loseConnection()
		if self.factory:
			self.factory.lostConnection(self)
	
	def write(self,val):
		self.transport.write(val+self.delimiter)


#class Nets(Collection):
#	name = "net"
#Nets = Nets()
#Nets.can_do("del")
#
#net_conns = {}

class NetCommonFactory(Collected):
	#protocol = NetReceiver
	#storage = Nets.storage
	#storage2 = net_conns
	typ = "???"

	def __init__(self, host="localhost", port=4304, name=None, *a,**k):
		if name is None:
			name = "%s:%s" % (host,port)

		self.conn = None
		self.host = host
		self.port = port
		self.name = name
		self.up_event = False
		assert (host,port) not in self.storage2, "already known host/port tuple"
		Collected.__init__(self)
		self.storage2[(host,port)] = self

	def info(self):
		return "%s %s: %s:%s" % (self.typ, self.name, self.host,self.port)
		
	def list(self):
		yield ("type",self.typ)
		yield ("host",self.host)
		yield ("port",self.port)
		yield ("connected", ("Yes" if self.conn is not None else "No"))

	def delete(self,ctx):
		assert self==self.storage2.pop((self.host,self.port))
		self.end()
		self.delete_done()


	def haveConnection(self,conn):
		self.drop()
		self.conn = conn

		if not self.up_event:
			self.up_event = True
			simple_event(Context(),"net","connect",*self.name)

	def lostConnection(self,conn):
		if self.conn == conn:
			self.conn = None
			self._down_event()

	def _down_event(self):
		if self.up_event:
			self.up_event = False
			simple_event(Context(),"net","disconnect",*self.name)

	def drop(self):
		"""Kill my connection"""
		if self.conn:
			self.conn.loseConnection()
		
	def write(self,val):
		if self.conn:
			self.conn.write(val)
		else:
			raise DisconnectedError(self.name)

	def end(self):
		c = self.conn
		self.conn = None
		if c:
			c.loseConnection()
			self._down_event()

class NetServerFactory(NetCommonFactory,protocol.ServerFactory):
	typ = "server"
	def end(self):
		try: self._port.stopListening()
		except AttribteError: pass # might be called twice
		del self._port
		super(NetServerFactory,self).end()

class NetClientFactory(NetCommonFactory,protocol.ClientFactory):
	typ = "client"
	def end(self):
		try: self.connector.stopConnecting()
		except error.NotConnectingError: pass
		del self.connector
		super(NetClientFactory,self).end()

	def clientConnectionFailed(self, connector, reason):
		log(WARN,reason)
		self.conn = None
		self._down_event()

	def clientConnectionLost(self, connector, reason):
		if not reason.check(error.ConnectionDone):
			log(INFO,reason)
		self.conn = None
		self._down_event()


class NetConnect(AttributedStatement):
	#name = ("net",)
	doc = "connect to a TCP port (base class)"
	dest = None
	#client = None # descendant of NetClientFactory

	@property
	def long_doc(self):
		return u"""\
You need to override the long_doc descroption of ‹%s›.
""" % (self.__class__.__name__,)

	def run(self,ctx,**k):
		event = self.params(ctx)
		if len(event) < 1+(self.dest is None) or len(event) > 2+(self.dest is None):
			raise SyntaxError(u"Usage: net ‹name› ‹host›? ‹port›")
		name = self.dest
		if name is None:
			name = Name(event[0])
			event = event[1:]
		if len(event) == 1:
			host = "localhost"
		else:
			host = event[0]
		port = event[-1]

		f = self.client(host=host, port=port, name=name)
		f.connector = reactor.connectTCP(host, port, f)


class NetListen(AttributedStatement):
	#name = ("listen","net")
	doc = "listen to a TCP socket (base class)"
	@property
	def long_doc(self):
		return u"""\
You need to override the long_doc descroption of ‹%s›.

"""
	dest = None
	#server = None # descendant of NetServerFactory

	def run(self,ctx,**k):
		event = self.params(ctx)
		if len(event) < 1+(self.dest is None) or len(event) > 2+(self.dest is None):
			raise SyntaxError(u"Usage: listen net ‹name› ‹host›? ‹port›")
		name = self.dest
		if name is None:
			name = Name(event[0])
			event = event[1:]
		if len(event) == 2:
			host = "localhost"
		else:
			host = event[1]
		port = event[-1]

		f = self.server(host=host, port=port, name=name)
		f._port = reactor.listenTCP(port, f, interface=host)


class NetName(Statement):
	name=("name",)
	dest = None
	doc="specify the name of a new TCP connection"

	@property
	def long_doc(self):
		return u"""\
%s ‹host› ‹port› :name ‹name…›
	: Use this form for multi-name network connections.
""" % (self.parent.name,)

	def run(self,ctx,**k):
		event = self.params(ctx)
		self.parent.dest = Name(event)
NetConnect.register_statement(NetName)
NetListen.register_statement(NetName)


class NetSend(AttributedStatement):
	#storage = Nets.storage
	#storage2 = net_conns
	#name=("send","net")
	dest = None
	doc="send a line to a TCP connection"
	long_doc=u"""\
send net ‹name› text…
	: The text is sent to the named net connection.
send net text… :to ‹name…›
	: as above, but works with a multi-word connection name.

"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		name = self.dest
		if name is None:
			name = Name(event[0])
			event = event[1:]

		val = u" ".join(unicode(s) for s in event)
		d = self.storage[name].write(val)
		return d

class NetTo(Statement):
	name=("to",)
	dest = None
	doc="specify which TCP connection to use"

	@property
	def long_doc(self):
		return u"""\
%s text… :to ‹name…›
	: Use this form for multi-name network connections.
""" % (self.parent.name,)

	def run(self,ctx,**k):
		event = self.params(ctx)
		self.parent.dest = Name(event)
NetSend.register_statement(NetTo)


class NetConnected(Check):
	#storage = Nets.storage
	#storage2 = net_conns
	name=("connected","net")
	doc="Test if a TCP connection is up"

	def check(self,*args):
		conn = None
		if len(args) == 2:
			conn = self.storage2.get(Name(args),None)
		if conn is None:
			conn = self.storage.get(Name(args))
		if conn is None:
			return False
		return conn.up_event

class NetExists(Check):
	#storage = Nets.storage
	#storage2 = net_conns
	#name=("exists","net")
	doc="Test if a TCP connection is configured"

	def check(self,*args):
		if len(args) == 2 and Name(args) in self.storage2:
			return True
		return Name(args) in self.storage

