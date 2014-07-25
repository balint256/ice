#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  lut.py
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

import res, utils
from constants import *

def parse_lut_text(lut):
	d = {}
	lines = lut.split('\n')
	if len(lines) <= 2:
		raise Exception("Invalid LUT text: \"%s\"" % (lut))
	for l in lines[2:]:	# Skip first two lines
		if len(l) == 0: continue	# Skip empty line (e.g. last)
		l = map(int, l.strip().split(','))
		d[l[0]] = l[1:]
	return d

# Not using these
# FIXME: Make into dictionary
#EMF_DS_LUT	= parse_emf_lut(res.EMF_DS_LUT_TXT)
# FIXME: Enable these once TXT is in 'res' (and it's useful)
#EMF_AS1_LUT	= parse_emf_lut(res.EMF_AS1_LUT_TXT)
#EMF_AS2_LUT	= parse_emf_lut(res.EMF_AS2_LUT_TXT)

get_ds_lut	= lambda x: gen_subcom_lut(len(EMF_COLS[DIGITAL_SUBCOM]),  EMF_SUBCOM_LEN, x, EMF_COLS[DIGITAL_SUBCOM])
get_as1_lut	= lambda x: gen_subcom_lut(len(EMF_COLS[ANALOG_SUBCOM_1]), EMF_SUBCOM_LEN, x, EMF_COLS[ANALOG_SUBCOM_1])
get_as2_lut	= lambda x: gen_subcom_lut(len(EMF_COLS[ANALOG_SUBCOM_2]), EMF_SUBCOM_LEN, x, EMF_COLS[ANALOG_SUBCOM_2])

# FIXME: Supposed to be a helper for Element definitions
def gen_element_lut_with_subcom_lut(lut, offsets):
	d = {}
	for k in lut.keys():
		for o in offsets:
			if o in lut[k]:
				if k not in d.keys(): d[k] = []
				d[k] += [o]
	return d

# Assumes width < limit
# Returns dict indexed by minor frame
def gen_subcom_lut(width, limit, offsets, columns):
	if width >= limit:
		raise Exception("Width exceeds limit for LUT generation (%d >= %d)" % (width, limit))
	if not isinstance(offsets, list):
		offsets = [offsets]
	d = {}
	x = 0
	for i in range(NUM_MINOR_FRAMES):
		x2 = (x + width) % limit	# Subcom index at beginning of next minor frame
		cnt = 0
		for o in offsets:
			if isinstance(o, list):
				# If continuous subcom bytes are required, pick the highest [last] one here
				o = max(o)
				#o = o[-1]	# This doesn't make sense when we assume that an element's bits/bytes should come out of the one subcom frame
			
			if (x2 > x and o >= x and o < x2) or (x2 < x and (((o >= x) and (o < limit)) or ((o >= 0) and (o < x2)))):
				if i not in d.keys(): d[i] = []
				col_idx = (o - x) % limit
				#if col_idx < 0 or col_idx >= len(columns): print "Out-of-bounds:", i, o, col_idx, x, x2, width, limit
				d[i] += [(cnt, o, col_idx, columns[col_idx])]
			cnt += 1
		x = x2
	return d

#def gen_lut_dict(v, cnt, pick_last=False):
def gen_lut_dict(v, cnt, pick_max=False):
	#if pick_last and isinstance(v, list):
	#	v = v[-1]
	if pick_max and isinstance(v, list):
		v = max(v)
	d = {}
	for i in range(cnt):
		d[i] = [(0, v, None, v)]
	return d

def combine_lut_dicts(*args):
	ks = utils.flatten([x.keys() for x in args])
	d = {}
	for k in set(ks):
		d[k] = utils.flatten([x[k] for x in args if k in x.keys()])
	return d

def main():
	return 0

if __name__ == '__main__':
	main()
