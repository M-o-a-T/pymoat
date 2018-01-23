# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division, unicode_literals
##
##  This file is part of MoaT, the Master of all Things.
##
##  MoaT is Copyright © 2007-2016 by Matthias Urlichs <matthias@urlichs.de>,
##  it is licensed under the GPLv3. See the file `README.rst` for details,
##  including optimistic statements by the author.
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
##  This header is auto-generated and may self-destruct at any time,
##  courtesy of "make update". The original is in ‘scripts/_boilerplate.py’.
##  Thus, do not remove the next line, or insert any blank lines above.
##BP

"""Helper code for scripting"""

from importlib import import_module
import os
import pkgutil
from etcd_tree import EtcXValue

from moat.task import TASK_DATA, TASKDEF_DIR

from . import CommandError

import logging
logger = logging.getLogger(__name__)

complained = set()

def rkeys(d,sub=''):
    if sub:
        sub += '/'
    for k,v in d.items(raw=True):
        if isinstance(v,EtcXValue):
            yield sub+k
        else:
            yield from rkeys(v,sub+k)
    
def objects(module, cls, immediate=False,direct=False,filter=lambda x:True):
    """\
        List all objects of a given class in a directory.

        If @immediate is set, only direct subclasses are returned.
        If @direct is set, modules in subdirectories are ignored.
        """
    def _check(m):
        try:
            if isinstance(m,str):
                m = import_module(m)
        except ModuleNotFoundError:
            pass
        except ImportError as ex:
            if m not in complained:
                complained.add(m)
                logger.exception(m)
        else:
            try:
                syms = m.__all__
            except AttributeError:
                syms = dir(m)
            for c in syms:
                c = getattr(m,c,None)
                if isinstance(c,type) and \
                        ((c.__base__ is cls) if immediate else (c is not cls and issubclass(c,cls))):
                    if filter(c):
                        yield c
            
    if isinstance(module,str):
        from qbroker.util import import_string
        module = import_string(module)
    yield from _check(module)
    for a,b,c in pkgutil.walk_packages((os.path.dirname(module.__file__),), module.__name__+'.'):
        if direct and a.path != module.__path__[0]:
            continue
        yield from _check(b)


class _ParamCommand:
    """\
        This is a customizeable mix-in for parameter setting.
        """
    name = "param"
    # _def = None ## need to override
    _make = False # create dir if missing?  used by web param
    def description(self,meta=False):
        return """\

This command shows/changes/deletes parameter%ss for that data.

Usage: … param WHAT NAME=VALUE… -- set
       … param                  -- list everything
       … param WHAT             -- list all
       … param WHAT NAME        -- show one
       … param -d WHAT NAME     -- delete one
""" % (" type" if meta else "",)
    DEPTH=0

    def addOptions(self):
        self.parser.add_option('-d','--delete',
            action="store_true", dest="delete",
            help="delete specific parameters")
        if hasattr(self,'_global'):
            self.parser.add_option('-g','--global',
                action="store_true", dest="is_global",
                help="access global parameters")

    async def do(self,args):
        if not hasattr(self,'_global'):
            self.options.is_global = False

        t = await self.setup(meta=self._def)
        if self.options.is_global:
            if self.options.delete:
                raise CommandError("You cannot delete global parameters.")
            data = self._global
        elif not args:
            if self._def and self.options.delete:
                raise CommandError("You cannot delete all parameters.")

            async for task in t.tagged(self.TAG,depth=self.DEPTH):
                path = task.path[len(self.DIR):-1]
                if TASK_DATA in task:
                    async for n in task[TASK_DATA].tagged(tag=None):
                        # …/:taskdef/data/…
                        print('/'.join(path),'/'.join(n.path[len(TASKDEF_DIR)+len(path)+2:]),n.value, sep='\t',file=self.stdout)
            return
        else:
            name = args.pop(0)
            try:
                task = await t.subdir(name, name=self.TAG, create=None if self._make else False)
            except KeyError:
                raise CommandError("Definition '%s' is unknown." % name)
            data = task[TASK_DATA]
        if self.options.delete:
            if not args:
                args = rkeys(data)
            for k in args:
                v = data.lookup(k)
                if self.root.verbose:
                    print("%s=%s (deleted)" % (k,v.value), file=self.stdout)
                await v.delete()
        elif len(args) == 1 and '=' not in args[0]:
            print(data.lookup(args[0]).value, file=self.stdout)
        elif not len(args):
            for k in rkeys(data):
                print(k,data.get(k), sep='\t',file=self.stdout)
        else:
            while args:
                k = args.pop(0)
                try:
                    k,v = k.split('=',1)
                except ValueError:
                    print(k,data.get(k,'-'), sep='\t',file=self.stdout)
                else:
                    if self.root.verbose:
                        if k not in data:
                            print("%s=%s (new)" % (k,v), file=self.stdout)
                        elif str(data[k]) == v:
                            print("%s=%s (unchanged)" % (k,v), file=self.stdout)
                        else:
                            print("%s=%s (was %s)" % (k,v,data[k]), file=self.stdout)
                    await data.set(k, v, ext=True)

#class DefParamCommand(_ParamCommand):
#    _def = True
#    DIR=TASKDEF_DIR
#    TAG=TASKDEF
#    summary = "Parameterize task definitions"
#    description = """\
#Task definitions are stored in etcd at /meta/task/**/:taskdef.
#""" + _ParamCommand.description
#
#class ParamCommand(_ParamCommand):
#    _def = False
#    DIR=TASK_DIR
#    TAG=TASK
#    summary = "Parameterize tasks"
#    description = """\
#Tasks are stored in etcd at /task/**/:task.
#""" + _ParamCommand.description
#
