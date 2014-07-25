#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  spin_rate.py
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

def spinrate(dsi34, dsi35):
	word34 = "{0:08b}".format(dsi34)
	word35 = "{0:08b}".format(dsi35)
	
	words = word34 + word35
	
	value = int(words, 2)
	#if value == 0:
	#	return False
	spinrate = 491520 / float(value)
	
	return spinrate

def spinperiod(dsi34, dsi35):
	word34 = "{0:08b}".format(dsi34)
	word35 = "{0:08b}".format(dsi35)
	
	words = word34 + word35
	
	value = int(words, 2)
	
	spinperiod = value / float(8192)
	
	return spinperiod

def magrate(dsi38, dsi39):
	word38 = "{0:08b}".format(dsi38)
	word39 = "{0:08b}".format(dsi39)
	
	words = word38 + word39
	
	value = int(words, 2)
	#if value == 0:
	#	return False
	magrate = 491520 / float(value)
	
	return magrate

def magperiod(dsi38, dsi39):
	word38 = "{0:08b}".format(dsi38)
	word39 = "{0:08b}".format(dsi39)
	
	words = word38 + word39
	
	value = int(words, 2)
	
	magperiod = value / float(8192)
	
	return magperiod

def spinangle(dsi32, dsi33, dsi34, dsi35):
	word32 = "{0:08b}".format(dsi32)
	word33 = "{0:08b}".format(dsi33)
	word34 = "{0:08b}".format(dsi34)
	word35 = "{0:08b}".format(dsi35)

	word32_33 = word32 + word33
	word34_35 = word34 + word35

	denom = int(word34_35, 2)
	#if denom == 0:
	#	return False
	spinangle = (float(int(word32_33, 2)) / float(denom)) * 360.0
	
	return spinangle
