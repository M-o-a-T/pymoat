# -*- coding: utf-8 -*-

"""Class to make storing collections of stuff simpler"""

from homevent.base import Name

from weakref import WeakValueDictionary,proxy

collections = WeakValueDictionary()


class Collection(dict):
	"""\
		This class implements named collections of things.

		Usage:
		
			class FooThings(Collection):
				name = "foo bar"
			FooThings = FooThings()

			class Foo(Collected):
				storage = FooThings.storage

		A subsequent "list foo bar" command enumerates all known Foo objects.

		"""

	def __repr__(self):
		try:
			return u"‹Collection %s›" % (self.__class__.__name__,)
		except Exception:
			return "<Collection:%s>" % (self.__class__.__name__,)

	def __init__(self):
		name = self.name
		if isinstance(name,basestring):
			name = name.split()
		name = Name(name)
		self.name = name
		if name in collections:
			return RuntimeError(u"A collection ‹%s› already exists" %(name,))
	
		collections[name] = self

	# The Collected's storage needs to be a weak reference so that it
	# will be freed when the module is unloaded.
	@property
	def storage(self):
		return proxy(self)

	
class Collected(object):
	"""\
		This abstract class implements an object in a named subsystem
		which has a name and can be "list"ed and "del"eted.

		self.name can be set explicitly, before calling super().__init__(),
		if passing the name would be inconvenient due to multiple inheritance.

		You need to assign foo.storage to the "storage" class attribute,
		where foo is the associated Collection object.
		"""
	storage = None # Collection

	def __init__(self, *name):
		if not name:
			name = self.name
		if not name:
			raise RuntimeError("Unnamed object of '%s'" % (self.__class__.__name__,))
			
		if self.storage is None:
			raise RuntimeError("You didn't declare a storage for '%s'" % (self.__class__.__name__,))

		self.name = name = Name(name)
		if name in self.storage:
			raise RuntimeError(u"Duplicate entry ‹%s› in ‹%s›" % (name,self.storage.name))
		self.storage[name] = self

	def __repr__(self):
		try:
			return u"‹Collected %s:%s›" % (self.__class__.__name__,self.name)
		except Exception:
			return "<Collected:%s>" % (self.__class__.__name__,)

	def list(self):
		"""Yield a couple of (left,right) tuples, for enumeration."""
		raise NotImplementedError("You need to override 'list' in '%s'" % (self.__class__.__name__,))

	def delete(self):
		"""Remove myself from a collection"""
		raise NotImplementedError("You need to override 'del' in '%s'" % (self.__class__.__name__,))

	def info(self):
		"""\
			Return a one-line string with additional data (but not the name!),
			if that makes sense.
			"""
		return None


class CKeyError(KeyError):
	def __init__(self,name,coll):
		self.name = name
		self.coll = coll
	def __repr__(self):
		return u"I could not find an entry for ‹%s› in %s." % (Name(self.name),self.coll)
	def __unicode__(self):
		return u"I could not find an entry for ‹%s› in %s." % (Name(self.name),self.coll)
	def __str__(self):
		return "I could not find an entry for ‹%s› in %s." % (Name(self.name),self.coll)

def get_collect(name):
	c = None
	if not len(name):
		return None
	coll = collections

	while len(name):
		n = len(name)
		while n > 0:
			try:
				coll = coll[Name(name[:n])]
			except KeyError:
				n = n-1
			else:
				name = name[n:]
				if c is None: c = coll
				break

		if n == 0:
			try:
				coll = coll[name[0]]
			except KeyError:
				raise CKeyError(name,c)
			else:
				name = name[1:]
				if c is None: c = coll
	return coll

def all_collect(attr="list"):
	for m in collections.itervalues():
		yield m