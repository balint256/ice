#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  fss_angle.py
#  
#  Copyright 2014 Jacob Gold
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

import math

def shifting(bitlist):
	out = 0
	for bit in bitlist:
		out = (out << 1) | bit
	return out

def gray2bin(bits):
	b = [bits[0]]
	for nextb in bits[1:]: b.append(b[-1] ^ nextb)
	return b

def fssangle(v01, v02, v03, vs, vc, vb, verbose=False):
	#changes numbers from INT to DEC
	v01 = v01 * 0.02
	v02 = v02 * 0.02
	v03 = v03 * 0.02
	vs = vs * 0.02
	vc = vc * 0.02
	vb = vb * 0.02
	
	#lambda coarse truth table
	coarse = []
	
	if v01 <= 0.2:
		coarse.append(0)
		coarse.append(0)
		coarse.append(0)
	elif 0.52 <= v01 <= 0.92:
		coarse.append(0)
		coarse.append(0)
		coarse.append(1)
	elif 1.23 <= v01 <= 1.63:
		coarse.append(0)
		coarse.append(1)
		coarse.append(0)
	elif 1.95 <= v01 <= 2.35:
		coarse.append(0)
		coarse.append(1)
		coarse.append(1)
	elif 2.66 <= v01 <= 3.06:
		coarse.append(1)
		coarse.append(0)
		coarse.append(0)
	elif 3.38 <= v01 <= 3.78:
		coarse.append(1)
		coarse.append(0)
		coarse.append(1)
	elif 4.09 <= v01 <= 4.59:
		coarse.append(1)
		coarse.append(1)
		coarse.append(0)
	elif 4.8 <= v01 <= 5.2:
		coarse.append(1)
		coarse.append(1)
		coarse.append(1)
	else:
		return 'Data out of expected range'
	
	if v02 <= 0.2:
		coarse.append(0)
		coarse.append(0)
	elif 1.23 <= v02 <= 1.63:
		coarse.append(0)
		coarse.append(1)
	elif 2.66 <= v02 <= 3.06:
		coarse.append(1)
		coarse.append(0)
	elif 4.09 <= v02 <= 4.59:
		coarse.append(1)
		coarse.append(1)
	else:
		return 'Data out of expected range'
	
	if v03 <= 0.2:
		coarse.append(0)
		coarse.append(0)
	elif 1.23 <= v03 <= 1.63:
		coarse.append(0)
		coarse.append(1)
	elif 2.66 <= v03 <= 3.06:
		coarse.append(1)
		coarse.append(0)
	elif 4.09 <= v03 <= 4.59:
		coarse.append(1)
		coarse.append(1)
	else:
		return 'Data out of expected range'
	
	#convert lambda coarse to binary
	
	coarse_bin = range(7)
	coarse_bin[0] = coarse[0]
	
	coarse_bin = gray2bin(coarse)

	#calculate lambda fine and convert to BIN
	
	fine = math.fabs( (1/math.pi) * math.atan((vs-vb) / (vc-vb)))
	
	if verbose: print fine
	fine_store = fine
	
	fine_bin = range(8)
	
	angle = 1
	
	for i in range(0,8):
		
		if angle <= fine:
			fine_bin[i] = 1
			fine = fine - angle
		else:
			fine_bin[i] = 0
		
		angle = angle / float(2)
		
	#add or subtract 1 from coarse based on MSBs of fine
	
	if verbose: print fine_bin
	if verbose: print coarse_bin
	
	if coarse_bin[6] == fine_bin[0]:
		coarse = shifting(coarse_bin)
	elif fine_bin[1] == 1:
		coarse = shifting(coarse_bin) - 1
	elif fine_bin[1] == 0:
		coarse = shifting(coarse_bin) + 1
	
	#add six MSBs of coarse to fine angle
	
	if verbose: print coarse
	
	if verbose: print coarse_bin
	if verbose: print coarse
	if verbose: print fine_store
	
	alpha = coarse + fine_store
	
	if verbose: print alpha
	beta = 154 - alpha
	
	return beta
