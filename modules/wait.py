#!/usr/bin/python
# -*- coding: utf-8 -*-

"""\
This code does basic timeout handling.

wait FOO...
	- waits for FOO seconds

"""

from homevent.statement import AttributedStatement, Statement, main_words,\
	global_words
from homevent.event import Event
from homevent.run import process_event
from homevent.logging import log,TRACE
from homevent.module import Module
from homevent.worker import HaltSequence
from homevent.time import time_delta
from homevent.check import Check,register_condition,unregister_condition
from time import time
import os
from twisted.python.failure import Failure

from twisted.internet import reactor,defer


timer_nr = 0
waiters={}


class WaitCancelled(RuntimeError):
	"""An error signalling that a wait was killed."""
	pass

class DupWaiterError(RuntimeError):
	"""A waiter with that name already exists"""
	pass

class WaitHandler(AttributedStatement):
	name=("wait",)
	doc="delay for N seconds"
	long_doc="""\
wait FOO...
	- delay processsing for FOO seconds
	  append "s/m/h/d/w" for seconds/minutes/hours/days/weeks
	  # you can do basic +/- calculations (2m - 10s); you do need the spaces
"""
	is_update = False

	def __init__(self,*a,**k):
		super(WaitHandler,self).__init__(*a,**k)
		global timer_nr
		timer_nr += 1
		self.nr = timer_nr
		self.displayname=("_wait",str(self.nr))

	def run(self,ctx,**k):
		event = self.params(ctx)
		s = time_delta(event)
					
		if self.is_update:
			if s < 0: s = 0
			w = waiters[self.displayname]
			w.retime(s)
			return
			
		if s < 0:
			log(TRACE,"No time out:",s)
			return # no waiting
		log(TRACE,"Timer",self.nr,"::",s)

		r = defer.Deferred()
		if self.displayname in waiters:
			raise DupWaiterError(self.displayname)
		waiters[self.displayname] = self
		self.timer_start=time()
		self.timer_val = s
		self.timer_defer = r
		self.timer_id = reactor.callLater(s, self.doit)
		return r
	
	def get_value(self):
		val = self.timer_start+self.timer_val-time()
		if "HOMEVENT_TEST" in os.environ:
			return int(val+1) # otherwise the logs will have timing diffs
		return val
		
	value = property(get_value)

	def doit(self):
		log(TRACE,"Timeout",self.nr)
		del waiters[self.displayname]
		r = self.timer_defer
		self.timer_defer = None
		r.callback(None)

	def cancel(self, err=WaitCancelled):
		self.timer_id.cancel()
		self.timer_id = None
		del waiters[self.displayname]
		self.timer_defer.errback(Failure(err(self)))
	
	def retime(self, timeout):
		self.timer_id.cancel()
		self.timer_val = time()-self.timer_start+timeout
		self.timer_id = reactor.callLater(timeout, self.doit)


class WaitName(Statement):
	name = ("name",)
	doc = "name a wait handler"
	long_doc="""\
This statement assigns a name to a wait statement
(Useful when you want to cancel it later...)
"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if not len(event):
			raise SyntaxError('Usage: name ‹name…›')
		self.parent.displayname = tuple(event)


class WaitCancel(Statement):
	name = ("del","wait")
	doc = "abort a wait handler"
	long_doc="""\
This statement aborts a wait handler.
"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if not len(event):
			raise SyntaxError('Usage: del wait ‹name…›')
		w = waiters[tuple(event)]
		w.cancel(err=HaltSequence)

class WaitUpdate(Statement):
	name = ("update",)
	doc = "change the timeout of an existing wait handler"
	long_doc="""\
This statement updates the timeout of an existing wait handler.
"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if len(event):
			raise SyntaxError('Usage: update')
		assert hasattr(self.parent,"is_update"), "Not within a wait statement?"
		self.parent.is_update = True


class WaitList(Statement):
	name=("list","wait")
	doc="list of waiting statements"
	long_doc="""\
list wait
	shows a list of running wait statements.
list wait NAME
	shows details for that wait statement.
	
"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if not len(event):
			for w in waiters.itervalues():
				print >>self.ctx.out, " ".join(w.displayname)
			print >>self.ctx.out, "."
		else:
			w = waiters[tuple(event)]
			print  >>self.ctx.out, "Name: "," ".join(w.displayname)
			print  >>self.ctx.out, "Started: ",w.timer_start
			print  >>self.ctx.out, "Timeout: ",w.timer_val
			print  >>self.ctx.out, "Remaining: ",w.timer_start+w.timer_val-time()
			while True:
				w = getattr(w,"parent",None)
				if w is None: break
				n = getattr(w,"displayname",None)
				if n is not None:
					n = " ".join(n)
				else:
					try:
						n = str(w.args)
					except AttributeError:
						pass
					if n is None:
						try:
							n = " ".join(w.name)
						except AttributeError:
							n = w.__class__.__name__
				if n is not None:
					print  >>self.ctx.out, "in: ",n
			print  >>self.ctx.out, "."

class ExistsWaiterCheck(Check):
	name=("exists","wait")
	doc="check if a waiter exists at all"
	def check(self,*args):
		if not len(args):
			raise SyntaxError("Usage: if exists wait ‹name…›")
		name = tuple(args)
		return name in waiters


class VarWaitHandler(Statement):
	name=("var","wait")
	doc="assign a variable to report when a waiter will time out"
	long_doc="""\
var wait NAME name...
	: $NAME tells how many seconds in the future the wait record ‹name…›
	  will trigger
"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		w = event[:]
		var = w[0]
		name = tuple(w[1:])
		setattr(self.parent.ctx,var,waiters[name])


WaitHandler.register_statement(WaitName)
WaitHandler.register_statement(WaitUpdate)


class EventsModule(Module):
	"""\
		This module contains basic event handling code.
		"""

	info = "Basic event handling"

	def load(self):
		main_words.register_statement(WaitHandler)
		main_words.register_statement(WaitCancel)
		main_words.register_statement(VarWaitHandler)
		global_words.register_statement(WaitList)
		register_condition(ExistsWaiterCheck)
	
	def unload(self):
		main_words.unregister_statement(WaitHandler)
		main_words.unregister_statement(WaitCancel)
		main_words.unregister_statement(VarWaitHandler)
		global_words.unregister_statement(WaitList)
		unregister_condition(ExistsWaiterCheck)

init = EventsModule
