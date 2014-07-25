#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  utils.py
#  
#  Copyright 2014 Balint Seeber <balint256@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

class Callable:
	def __init__(self, anycallable):
		self.__call__ = anycallable

def bits_to_bytes(offsets, unique=False, sort=False):
	l = []
	for o in offsets:
		if isinstance(o, list):
			l += [bits_to_bytes(o, unique, sort)]
		else:
			b = o / 8
			if (not unique) or (b not in l):
				l += [b]
	if sort:
		return sorted(l)
	return l

def interpolate(val, curve):
	# Check val in valid input range
	curve_in, curve_out = curve[0], curve[1]
	if len(curve_in) != len(curve_out):
		raise Exception("Curves in and out are not of equal length: %s" % (curve))
	#if val < min(curve_in) or val > max(curve_in):
	if curve_in[0] != min(curve_in) or curve_in[-1] != max(curve_in):
		raise Exception("Invalid ordering in in curve: %s" % (curve))
	if val < curve_in[0] or val > curve_in[-1]:
		return (False, val)
	# Interpolate
	for x1, x2, y1, y2 in zip(curve_in, curve_in[1:], curve_out, curve_out[1:]):
		if val >= x1 and val <= x2:
			t = (1.*val - x1) / (1.*x2 - x1)
			return (True, 1.*y1 + (t * (y2 - y1)))
	# Shouldn't get here
	raise Exception("Failed to interpolate curve %s with value %s" % (curve, val))

def find_subclass(c, l, return_all=False):
	m = []
	if not isinstance(l, list): l = [l]
	for _l in l:
		if not _l: continue
		if issubclass(_l.__class__, c): m += [_l]
	if len(m) == 0: return None
	if return_all:
		return m
	#if len(m) > 1: return None	# [Only allow one match] (no longer doing this: specific order set in lists below, i.e. 'positions' is last)
	return m[0]

def num_range(start, stop): return range(start, stop + 1)	# [start, end] (inclusive)

def flatten(l): return [i for subl in l for i in subl]

def main():
	return 0

if __name__ == '__main__':
	main()
