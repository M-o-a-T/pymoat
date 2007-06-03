# -*- coding: utf-8 -*-

from __future__ import division

"""\
This code does basic configurable event mangling.

on switch *state livingroom *switch:
	send change $state lights livingroom $switch

on switch * * *:
	if neq $2 outside
	if state on alarm internal
	trigger alarm $2

Given the event "switch on livingroom main", this would cause a
"change on lights livingroom main" event if the internal alarm is off.
Otherwise a "alarm livingroom" would be triggered.

"""

from homevent.interpreter import CollectProcessor
from homevent.statement import Statement,MainStatementList, main_words,\
	global_words
from homevent.logging import log_event,log, TRACE
from homevent.run import register_worker,unregister_worker,MIN_PRIO,MAX_PRIO
from homevent.worker import HaltSequence,Worker
from homevent.module import Module
from homevent.logging import log

from twisted.internet import defer

onHandlers = {}
onHandlerNames = {}
_onHandler_id = 0


class BadArgs(RuntimeError):
	def __str__(self):
		return "Mismatch: %s does not fit %s" % (repr(self.args[0]),repr(self.args[1]))

class BadArgCount(RuntimeError):
	def __str__(self):
		return "The number of event arguments does not match"

class OnEventHandler(MainStatementList,Worker):
	name=("on",)
	doc="on [event...]: [statements]"
	long_doc="""\
The OnEvent handler executes a statement (or a statement sequence)
when an event occurs.

Syntax:
	on [event...]:
		statement
		...

Every "*foo" in the event description is mapped to the corresponding
"$foo" argument in the list.
"""
	in_sub = False
	prio = (MIN_PRIO+MAX_PRIO)//2+1
	displayname = None

	def does_event(self,event):
		ie = iter(event)
		ia = iter(self.args)
		ctx = {}
		pos = 0
		while True:
			try: e = ie.next()
			except StopIteration: e = StopIteration
			try: a = ia.next()
			except StopIteration: a = StopIteration
			if e is StopIteration and a is StopIteration:
				return True
			if e is StopIteration or a is StopIteration:
				return False
			if a.startswith('*'):
				if a == '*':
					pos += 1
					a = str(pos)
				else:
					a = a[1:]
				ctx[a] = e
			elif a != e:
				return False

	def grab_args(self,event,ctx):
		ie = iter(event)
		ia = iter(self.args)
		pos = 0
		while True:
			try: e = ie.next()
			except StopIteration: e = StopIteration
			try: a = ia.next()
			except StopIteration: a = StopIteration
			if e is StopIteration and a is StopIteration:
				return
			if e is StopIteration or a is StopIteration:
				raise BadArgCount
			if a.startswith('*'):
				if a == '*':
					pos += 1
					a = str(pos)
				else:
					a = a[1:]
				setattr(ctx,a,e)
			elif a != e:
				raise BadArgs(a,e)
		
	def process(self,event,**k):
		ctx = self.ctx(ctx=event.ctx)
		self.grab_args(event,ctx)
		return super(OnEventHandler,self).run(ctx,**k)

	def run(self,ctx,**k):
		if self.procs is None:
			raise SyntaxError("‹on ...› can only be used as a complex statement")

		global _onHandler_id
		_onHandler_id += 1
		self.handler_id = _onHandler_id
		log(TRACE,"NewHandler",self.handler_id)
		self.name = "¦".join(self.args)
		if self.displayname is not None:
			self.name += " ‹"+self.displayname+"›"
		register_worker(self)
		onHandlers[self.handler_id] = self
		if self.displayname is not None:
			onHandlerNames[self.displayname] = self

	def start_block(self):
		super(OnEventHandler,self).start_block()
		w = self.params(self.ctx)[:]
		log(TRACE, "Create OnEvtHandler: "+repr(w))
		self.args = w


class OffEventHandler(Statement):
	name = ("del","on")
	doc = "forget about an event handler"
	def run(self,ctx,**k):
		event = self.params(ctx)
		if len(event) == 1:
			try: worker = onHandlers[event[0]]
			except KeyError: worker = onHandlerNames[event[0]]
			unregister_worker(worker)
			del onHandlers[worker.handler_id]
			if worker.displayname is not None:
				del onHandlerNames[worker.displayname]
		else:
			raise SyntaxError("Usage: del on ‹handler_id/name›")

class OnListHandler(Statement):
	name = ("list","on")
	doc = "list event handlers"
	def run(self,ctx,**k):
		event = self.params(ctx)
		if not len(event):
			try:
				fl = len(str(max(onHandlers.iterkeys())))
			except ValueError:
				pass # max() on an empty sequence
			else:
				for id in sorted(onHandlers.iterkeys()):
					h = onHandlers[id]
					n = "¦".join(h.args)
					if h.displayname is not None:
						n += " ‹"+h.displayname+"›"
					print >>self.ctx.out,str(id)+" "*(fl-len(str(id))+1),":",n
			print >>self.ctx.out,"."
		elif len(event) == 1:
			try: h = onHandlers[event[0]]
			except KeyError: h = onHandlerNames[event[0]]
			print >>self.ctx.out, h.handler_id,":","¦".join(h.args)
			if h.displayname is not None: print >>self.ctx.out,"Name:",h.displayname
			if hasattr(h,"displaydoc"): print >>self.ctx.out,"Doc:",h.displaydoc
		else:
			raise SyntaxError("Usage: list on ‹handler_id›")


class OnPrio(Statement):
	name = ("prio",)
	doc = "prioritize event handler"
	immediate = True
	long_doc="""\
This statement prioritizes an event handler.
Only one handler within each priority is actually executed.
"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if len(event) != 1:
			raise SyntaxError("Usage: prio ‹priority›")
		try:
			prio = int(event[0])
		except ValueError:
			raise SyntaxError("Usage: prio ‹priority› ⇐ integer priorities only")
		if prio < MIN_PRIO or prio > MAX_PRIO:
			raise ValueError("Priority value (%d): needs to be between %d and %d" % (prio,MIN_PRIO,MAX_PRIO))
		self.parent.prio = prio


class OnName(Statement):
	name = ("name",)
	doc = "name an event handler"
	immediate = True
	long_doc="""\
This statement assigns a name to an event handler.
(Useful when you want to delete it...)
"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if len(event) != 1:
			raise SyntaxError('Usage: name "‹text›"')
		self.parent.displayname = event[0]


class OnDoc(Statement):
	name = ("doc",)
	doc = "document an event handler"
	immediate = True
	long_doc="""\
This statement assigns a documentation string to an event handler.
(Useful when you want to document what the thing does ...)
"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if len(event) != 1:
			raise SyntaxError('Usage: doc "‹text›"')
		self.parent.displaydoc = event[0]


class OnSkip(Statement):
	name = ("skip","next")
	doc = "skip later event handlers"
	long_doc="""\
This statement causes higher-priority handlers to be skipped.
NOTE: Commands in the same handler, after this one, *are* executed.
"""
	def run(self,ctx,**k):
		raise HaltSequence()


class OnEventModule(Module):
	"""\
		This module registers the "on EVENT:" handler.
		"""

	info = "the 'on EVENT:' handler"

	def load(self):
		main_words.register_statement(OnEventHandler)
		main_words.register_statement(OffEventHandler)
		global_words.register_statement(OnListHandler)
		OnEventHandler.register_statement(OnPrio)
		main_words.register_statement(OnSkip)
		OnEventHandler.register_statement(OnName)
		OnEventHandler.register_statement(OnDoc)
	
	def unload(self):
		main_words.unregister_statement(OnEventHandler)
		main_words.unregister_statement(OffEventHandler)
		global_words.unregister_statement(OnListHandler)
		OnEventHandler.unregister_statement(OnPrio)
		main_words.unregister_statement(OnSkip)
		OnEventHandler.unregister_statement(OnName)
		OnEventHandler.unregister_statement(OnDoc)
	
init = OnEventModule
