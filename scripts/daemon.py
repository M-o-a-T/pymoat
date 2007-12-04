#!/usr/bin/python2.5
# -*- coding: utf-8 -*-

import sys; sys.excepthook = None; del sys

from homevent.statement import main_words, global_words, Statement
from homevent.module import Load,Unload,LoadDir,ModuleExists,load_module
from homevent.check import register_condition
from homevent.context import Context
from homevent.parser import read_config
from homevent.run import process_failure
from homevent.twist import deferToLater,track_errors
from homevent.reactor import ShutdownHandler,mainloop,shut_down,\
	stop_mainloop
from homevent.logging import TRACE,DEBUG,INFO,WARN,ERROR,PANIC,\
	Logger,register_logger,LogNames
from signal import signal,SIGINT,SIGHUP,SIGQUIT
import sys

from twisted.internet import reactor,defer

main_words.register_statement(Load)
main_words.register_statement(Unload)
main_words.register_statement(LoadDir)
register_condition(ModuleExists)
main_words.register_statement(ShutdownHandler)
load_module("ifelse")

from optparse import OptionParser
parser = OptionParser(conflict_handler="resolve")
parser.add_option("-h","--help","-?", action="help",
	help="print this help text")
parser.add_option("-t", "--trace", dest="debuglevel", action="store",
	help="trace level (TRACE,DEBUG,INFO,WARN,ERROR,PANIC,NONE)", default="PANIC")
parser.add_option("-s", "--stack", dest="stack", action="store_true",
	help="HomEvenT errors are logged with Python stack traces")

(opts, args) = parser.parse_args()
if not args:
	print >>sys.stderr,"You need at least one config file!"
	sys.exit(1)

class DoLogger(Logger):
	"""\
		This class implements one particular way to log things.
		"""
	def _log(self,level,txt):
		if txt != ".":
			print >>self.out,LogNames[level]+"> "+txt


if opts.debuglevel != "NONE":
	if opts.debuglevel == opts.debuglevel.upper() and \
			opts.debuglevel in globals():
		register_logger(DoLogger(level=globals()[opts.debuglevel]))
	else:
		raise KeyError("'%s' is not a debug level." % (opts.debuglevel,))

track_errors(opts.stack)

def _readcf():
	d = defer.succeed(None)
	c = Context()
	def rcf(_,fn):
		return read_config(c,fn)
	for f in args:
		d.addCallback(rcf,f)
	def err(_):
		process_failure(_)
		shut_down()
	d.addErrback(err)

def readcf():
	deferToLater(_readcf)

signal(SIGINT, lambda a,b: deferToLater(stop_mainloop))
signal(SIGQUIT,lambda a,b: deferToLater(shut_down))
signal(SIGHUP, lambda a,b: readcf())

readcf()
mainloop()

