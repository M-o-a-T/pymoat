# -*- coding: utf-8 -*-

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

from __future__ import division,absolute_import
from django.http import HttpResponseRedirect
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.views.generic import ListView,DetailView,CreateView,UpdateView,DeleteView
from django.forms import ModelForm,FloatField,TimeField,Textarea
from django.utils.translation import ugettext_lazy as _
from rainman.models import Site,UserForSite
from rainman.utils import get_request
from datetime import time,timedelta,datetime


def home(request):
	try:
		gu = request.user.get_profile()
	except (ObjectDoesNotExist,AttributeError):
		sites = set()
	else:
		sites = gu.sites.all()

	if not sites:
		if request.user.is_authenticated():
			return HttpResponseRedirect('/login/no_access')
		else:
			return HttpResponseRedirect('/login/?next=%s' % request.path)

	if len(sites) == 1:
		return HttpResponseRedirect('/site/%d' % list(sites)[0].id)

	return HttpResponseRedirect('/site/')

class NonNegativeFloatField(FloatField):
	def clean(self,val):
		val = super(NonNegativeFloatField,self).clean(val)
		if val < 0:
			raise ValidationError(_(u'must not be negative'))
		return val

def Delta(t):
	if isinstance(t,timedelta):
		return t
	return timedelta(0,(t.hour*60+t.minute)*60+t.second,t.microsecond)

class TimeDeltaField(TimeField):
	default_error_messages = {
		'invalid': _(u'Enter a valid time interval.')
	}

	def to_python(self, value):
		"""
		Validates that the input can be converted to a time. Returns a Python
		datetime.timedelta object.
		"""
		res = super(TimeDeltaField, self).to_python(value)
		return Delta(res)

	def strptime(self, value, format):
		return Delta(datetime.strptime(value, format).time())

class FormMixin(object):
	def get_template_names(self):
		return ["obj/%s%s.jinja" % (self.model._meta.object_name.lower(), self.template_name_suffix)]

