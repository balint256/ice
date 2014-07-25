#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  elems_shared.py
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

from primitives import *

class FixedWordParser(ByteParser):
	def __init__(self, fw_idx, bits=None, *args, **kwds):
		ByteParser.__init__(self, *args, **kwds)
		self.fw_idx = fw_idx
		if bits is not None and not isinstance(bits, list): bits = [bits]
		self.bits = bits
	def parse(self, val, *args, **kwds):
		fw_idx = kwds['minor_frame_idx'] % 4
		if fw_idx != self.fw_idx:
			return (False, None)
		(res, val) = ByteParser.parse(self, val, *args, **kwds)
		if res == False:
			return (res, val)
		if self.bits is None: return (True, val)
		v = 0
		for b in self.bits:
			v <<= 1
			if (val & (1 << (7-b))) != 0:
				v |= 1
		return (True, v)

def main():
	return 0

if __name__ == '__main__':
	main()
