# -*- coding: utf-8 -*-

"""\
We need code for conditionals.

test foo bar:
	true if state on what ever
	false

if test foo bar:
	do-something
else:
	do-something-else

on what ever:
	if test foo bar

This code implements the "if" command.
"""

from homevent.statement import MainStatementList,Statement, \
	main_words,global_words
from homevent.module import Module
from homevent.check import check_condition
from homevent import logging
from homevent.run import process_failure

from twisted.internet import defer
from twisted.python import failure
import sys

class RaisedError(RuntimeError):
	"""An error that has been explicitly raised by a script"""
	def __init__(self,*params):
		self.params = params
	def __repr__(self):
		return u"‹%s: %s›" % (self.__class__.__name__, repr(self.params))
	def __str__(self):
		return u"%s: %s" % (self.__class__.__name__, " ".join(map(str,self.params)))

class TryStatement(MainStatementList):
	name=("try",)
	doc="try: [statements]"
	long_doc="""\
The "try" statement executes a block, but continues after an error.

Syntax:
	try:
		statement
		...

"""
	in_sub = False
	displayname = None
	catch_do = None

	def add_catch(self,proc):
		if self.catch_do is None:
			self.catch_do = proc
		else:
			self.catch_do.add_catch(proc)
		
	def run(self,ctx,**k):
		want=True
		if self.procs is None:
			raise SyntaxError(u"‹if ...› can only be used as a complex statement")

		event = self.params(ctx)
		if len(event):
			raise SyntaxError("Usage: try: [Statements]")
		return self._run(ctx,**k)

	def _run(self,ctx,**k):
		d = super(TryStatement,self).run(ctx,**k)
		if self.catch_do:
			d.addErrback(lambda _: self.catch_do.run(ctx(error_=_), **k))
		else:
			d.addErrback(process_failure)
		return d


class CatchStatement(TryStatement):
	name=("catch",)
	doc="catch: [statements]"
	long_doc="""\
The "catch" statement executes a block only if a previous "try" block
(or the preceding "catch" block) errors out.

Syntax:
	try:
		statement
	catch:
		statement
		...

Implementation restriction: can't be used at top level. (Wrap with 'block:'.)
"""
	immediate = True

	def start_block(self):
		super(CatchStatement,self).start_block()
		self.arglist = self.params(self.ctx)[:]

	def does_error(self,ctx):
		err = ctx.error_
		ctx = ctx()
		if isinstance(err,failure.Failure):
			err = err.value
		if not isinstance(err,RaisedError):
			if len(self.arglist) > 1:
				return None
			if self.arglist:
				if err.__class__.__name__ != self.arglist[0] and not err.__class__.__name__.endswith("."+self.arglist[0]):
					return None
			return ctx
		elif len(self.arglist) == 0:
			pos = 0
			for p in err.params:
				pos += 1
				setattr(ctx,str(pos),p)
			return ctx
		ie = iter(err.params)
		ia = iter(self.arglist)
		pos = 0
		while True:
			try: e = ie.next()
			except StopIteration: e = StopIteration
			try: a = ia.next()
			except StopIteration: a = StopIteration
			if e is StopIteration and a is StopIteration:
				return ctx
			if e is StopIteration or a is StopIteration:
				return None
			if a.startswith('*'):
				if a == '*':
					pos += 1
					a = str(pos)
				else: 
					a = a[1:]
				setattr(ctx,a,e)
			elif a != e:
				return None

	def run(self,ctx,**k):
		if self.immediate:
			self.immediate = False
			self.parent.procs[-1].add_catch(self)
		else:
			c = self.does_error(ctx)
			if c:
				return self._run(c,**k)
			elif self.catch_do:
				return self.catch_do.run(ctx,**k)
			else:
				return defer.fail(ctx.error_)
	

class ReportStatement(Statement):
	name=("log","error")
	doc="log error [Severity]"
	long_doc="""\
If running in a "catch" block, this statement logs the current error.

Syntax:
	try:
		statement
	catch:
		log error WARN

"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if not len(event):
			level = logging.DEBUG
		elif len(event) == 1:
			try:
				level = getattr(logging,event[0].upper())
			except AttributeError:
				raise SyntaxError("unknown severity",event[0])
		else:
			raise SyntaxError("Usage: log error [severity]")
		logging.log_exc(msg="Logged:", err=ctx.error_, level=level)


class TriggerStatement(Statement):
	name=("trigger","error")
	doc=u"trigger error NAME…"
	long_doc=u"""\
This command causes an error to be reported.

The names are user-assigned; they'll be accessible as $1…$n in "catch" blocks.
Syntax:
	try:
		trigger error BAD StuffHappened
	catch:
		log WARN "Ouch:" $2

"""
	def run(self,ctx,**k):
		event = self.params(ctx)
		if not len(event):
			raise SyntaxError(u"Usage: trigger error NAME…")
		err = RaisedError(*event[:])
		logging.log_exc(msg="Triggered:", err=err, level=logging.TRACE)
		raise err


class ErrorsModule(Module):
	"""\
		This module implements the "if ...:" command.
		"""

	info = "try / catch"

	def load(self):
		main_words.register_statement(TryStatement)
		main_words.register_statement(CatchStatement)
		main_words.register_statement(ReportStatement)
		main_words.register_statement(TriggerStatement)
	
	def unload(self):
		main_words.unregister_statement(TryStatement)
		main_words.unregister_statement(CatchStatement)
		main_words.unregister_statement(ReportStatement)
		main_words.unregister_statement(TriggerStatement)
	
init = ErrorsModule