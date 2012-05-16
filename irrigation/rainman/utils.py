# -*- coding: utf-8 -*-

##
##  Copyright © 2012, Matthias Urlichs <matthias@urlichs.de>
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
	This module holds a few random utility functions.
	"""

from datetime import datetime
from django.utils.timezone import utc

def now():
	return datetime.utcnow().replace(tzinfo=utc)

# Work with date (or whatever) ranges.
class NotYet: pass
class StoredIter(object):
	def __init__(self,it):
		self.it = range_coalesce(it)
		self.saved = NotYet

	@property
	def next(self):
		self.saved = self.it.next()
		return self.saved
	@property
	def stored(self):
		if self.saved is NotYet:
			self.saved = self.it.next()
		return self.saved
		
def range_coalesce(it):
	"""Returns an iterator which returns the union of overlapping (start,lengt) pairs."""
	it = iter(it)
	ra,rl = it.next()
	while True:
		try:
			sa,sl = it.next()
		except StopIteration:
			yield ra,rl
			return
		assert ra <= sa
		re = ra+rl
		se = sa+sl

		if re < sa:
			yield ra,rl
			ra,rl=sa,sl
			continue
		if re < se:
			rl = se-ra


def range_merge(*a):
	"""\
		Return an iterator which yields a row of start+length tuples
		which are the intersection of all the start+length tuples in a.
		"""
	head = [StoredIter(ax) for ax in a]

	ra,rl = head[0].stored

	while True:
		found=True
		for ax in head:
			sa,sl = ax.stored
			while sa+sl <= ra:
				sa,sl = ax.next
			if rl is not None and ra+rl <= sa:
				ra,rl=sa,sl
				found=False
				break
			if ra<sa:
				if rl is None:
					rl=sl
				else:
					rl-=sa-ra
				ra=sa
			elif rl is None:
				rl=sl-(ra-sa)
			if ra+rl>sa+sl:
				rl=sa+sl-ra

			# test for rl<=0, except we don't know this type's zero
			# so restart at sa/sl
			if ra+rl<=ra:
				if sa < ra:
					rl = sl+sa-ra
				else:
					rl = sl
				ra = sa
				found=False
				break
		if found:
			yield (ra,rl)
			ra += rl
			rl = None

def range_invert(ra,rl,a):
	for sa,sl in a:
		if sa > ra+rl:
			return
		if sa+sl <= ra:
			continue
		if sa>ra:
			yield ra,sa-ra
			rl -= sa-ra + sl
			ra = sa+sl
		else:
			sl -= ra-sa
			ra += sl
			rl -= sl
	yield ra,rl

if __name__ == "__main__":
	a=((1,100),(220,100),(350,100),(500,100))
	b=((2,50),(60,100),(320,80),(510,110))
	c=((0,10),(11,2),(70,1000))
	print a
	print b
	print c
	print list(range_merge(a,b,c))
	print list(range_merge(c,b,a))
	print list(range_merge(c,a,b))
	print list(range_merge(a,c,b))
	print list(range_merge(b,c,a))
	print list(range_merge(b,a,c))
	print list(range_invert(50,950,a))
