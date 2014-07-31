#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  primitives.py
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

import math

import utils, state

from constants import *

class Parser():
	def __init__(self, *args, **kwds): pass
	def __call__(self, *args, **kwds): self.parse(*args, **kwds)
	def parse(self, l, *args, **kwds):
		raise Exception("Implement Parser")

class ShiftParser(Parser):
	def __init__(self, shift, *args, **kwds):
		Parser.__init__(self, *args, **kwds)
		self.shift = shift
	def parse(self, l, *args, **kwds):
		val = 0L
		for x in l:
			val <<= self.shift
			val |= x
		return (True, val)

class ByteParser(ShiftParser):
	def __init__(self, *args, **kwds):
		ShiftParser.__init__(self, 8, *args, **kwds)

class BitParser(ShiftParser):
	def __init__(self, *args, **kwds):
		ShiftParser.__init__(self, 1, *args, **kwds)

########################################

class RangeInfo():
	def __init__(self, rng, points=None):
		self.rng = rng
		self.points = points# or rng

########################################

class Validator():
	def __init__(self, *args, **kwds): pass
	def __call__(self, *args, **kwds): self.validate(*args, **kwds)
	def validate(self, value, *args, **kwds):
		return None	# Indeterminate

class RangeValidator(Validator, RangeInfo):
	def __init__(self, *args, **kwds):
		Validator.__init__(self, *args, **kwds)
		RangeInfo.__init__(self, *args, **kwds)
	def validate(self, val, *args, **kwds):
		if val < self.rng[0] or val > self.rng[-1]:
			return False
		return True

########################################

class Formatter():
	def __init__(self, *args, **kwds): pass
	def __call__(self, *args, **kwds): self.format(*args, **kwds)
	def format(self, val, *args, **kwds):
		return str(val)	# Perform the default conversion

class CustomFormatter(Formatter):
	def __init__(self, fmt, *args, **kwds):
		Formatter.__init__(self, *args, **kwds)
		self.fmt = fmt
	def format(self, val, *args, **kwds):
		return self.fmt % val

class FillFormatter(Formatter):
	def __init__(self, fn, fill=0, skip=0, round_up=False, *args, **kwds):
		Formatter.__init__(self, *args, **kwds)
		self.fn = fn
		self.fill = fill
		self.skip = skip
		self.round_up = round_up
	def format(self, val, *args, **kwds):
		#if val is None: return ""	# FIXME: When/where did this happen?
		s = self.fn(val)[self.skip:]
		fill = self.fill
		if self.round_up:
			fill = int(math.ceil(1.*len(s) / self.fill)) * self.fill
		return s.zfill(fill)

class BinaryFormatter(FillFormatter):
	def __init__(self, fill=8, skip=2, round_up=False, *args, **kwds): FillFormatter.__init__(self, bin, fill, skip, round_up, *args, **kwds)

# Alternatively:
#class BinaryFormatter(FillFormatter):
#	fn = bin # then use .fn

class HexFormatter(FillFormatter):
	def __init__(self, fill=2, skip=2, round_up=False, *args, **kwds): FillFormatter.__init__(self, hex, fill, skip, round_up, *args, **kwds)

class AutoFillFormatter(Formatter):
	def __init__(self, fn, div=1, skip=0, *args, **kwds):
		Formatter.__init__(self, *args, **kwds)
		self.fn = fn
		self.div = div
		self.skip = skip
	def format(self, val, *args, **kwds):
		fill = kwds['bit_count']	# FIXME
		fill /= div
		return self.fn(val)[self.skip:].zfill(fill)

class AutoBinaryFormatter(AutoFillFormatter):
	def __init__(self, skip=2, *args, **kwds): FillFormatter.__init__(self, bin, skip, *args, **kwds)

class AutoHexFormatter(AutoFillFormatter):
	def __init__(self, div=8, skip=2, *args, **kwds): FillFormatter.__init__(self, hex, div, skip, *args, **kwds)

class OptionFormatter(Formatter):
	def __init__(self, options, *args, **kwds):
		Formatter.__init__(self, *args, **kwds)
		self.options = options
	def format(self, val, *args, **kwds):
		if val < 0 or val >= len(self.options):
			return "<index out-of-range: %s>" % (val)
		return self.options[val]

class CurveFormatter(CustomFormatter, RangeInfo):
	def __init__(self, curve, fmt="%f", *args, **kwds):
		CustomFormatter.__init__(self, fmt, *args, **kwds)
		RangeInfo.__init__(self, curve[0], curve[1], *args, **kwds)
		self.curve = curve
	def format(self, val, *args, **kwds):
		#if val is None: return "-"	# FIXME: When/where did this happen?
		res, interp_val = utils.interpolate(val, self.curve)
		if not res:
			return "<out-of-range: %s>" % (interp_val)
		return CustomFormatter.format(self, interp_val)

class CurveFormatterValidator(CurveFormatter, RangeValidator):
	def __init__(self, curve, *args, **kwds):
		CurveFormatter.__init__(self, curve, *args, **kwds)
		RangeValidator.__init__(self, curve[0], curve[1], *args, **kwds)

########################################

class CustomOffset():
	def __init__(self, compatible_trackers, *args, **kwds):
		self.compatible_trackers = compatible_trackers
	#def get_compatible_trackers(self): return self.compatible_trackers
	def is_compatible_tracker(self, c):
		return issubclass(c.__class__, tuple(self.compatible_trackers))
	def get_trigger_indices(self, *args, **kwds):
		raise Exception("Implement CustomOffset get_trigger_offsets")
	def collect(self, *args, **kwds):
		raise Exception("Implement CustomOffset collect")

class ByteOffsetPrototype(CustomOffset):
	def __init__(self, offsets, byte_offsets=None, lut=None, auto_complete=True, *args, **kwds):
		CustomOffset.__init__(self, [state.FrameTracker])
		# [indices]
		# [[indices]] (as a group)
		# {minor_frame_idx: [flat list of: (cnt, offset, col_idx, idx)]} (either passed in, or generated by LUT)
		self.offsets = offsets
		self.byte_offsets = byte_offsets
		self.lut = lut	# Function should accept list of (indices | list of indices representing a group of which the highest is chosen). Returns {minor_frame_idx: [LUT(index)]}
		if auto_complete:
			self._complete_init(byte_offsets or offsets)
	def _complete_init(self, byte_offsets):
		if isinstance(byte_offsets, dict) and self.lut is not None:
			raise Exception("Cannot apply LUT to dictionary of offsets")
		
		self.byte_offsets_pre_lut = byte_offsets
		
		if self.lut: self.byte_offsets = self.lut(byte_offsets)
		else: self.byte_offsets = byte_offsets
		
		self.trigger_map = {}
		
		if isinstance(self.byte_offsets, list):	# Applies to all minor frames
			
			for byte_offset, offset in zip(self.byte_offsets, self.offsets):
				if isinstance(byte_offset, list):
					byte_offset_key = max(byte_offset)
				else:
					byte_offset_key = byte_offset
					byte_offset = [byte_offset]
				# Since this is kept independent of the FrameTracker's length, let the FrameTracker deal with the key not being a tuple (it will apply it to all minor frames)
				if not isinstance(offset, list): offset = [offset]
				trigger = state.Trigger(MINOR_FRAME_KEY, (byte_offset_key,))
				if trigger in self.trigger_map.keys():
					raise Exception("Byte offset key %s already in trigger map: %s" % (byte_offset_key, self.trigger_map[trigger]))
				self.trigger_map[trigger] = (byte_offset, offset, None)
		
		elif isinstance(self.byte_offsets, dict):
			
			if isinstance(self.offsets, dict):	# Single bytes only
				if self.byte_offsets != self.offsets:
					raise Exception("Expected offsets dict and byte offsets dict to be the same")
				
				for minor_frame_idx in self.byte_offsets.keys():
					for cnt, offset, col_idx, idx in self.byte_offsets[minor_frame_idx]:
						byte_offset_key = (minor_frame_idx, idx)
						trigger = state.Trigger(MINOR_FRAME_KEY, byte_offset_key)
						if trigger in self.trigger_map.keys():
							raise Exception("Byte offset key %s already in trigger map: %s" % (byte_offset_key, self.trigger_map[trigger]))
						self.trigger_map[trigger] = ([idx], [offset], None)
			
			elif isinstance(self.offsets, list):	# List was converted to dict with LUT
				raise Exception("This portion of the code is not finished")
				
				if self.lut is None:
					raise Exception("byte offset is a dict and offsets is a list, but no LUT")
				
				if not isinstance(self.byte_offsets_pre_lut, list):
					raise Exception("offsets is a list, but byte offsets passed in is not: %s" % (type(self.byte_offsets_pre_lut)))
				
				if len(self.offsets) != len(self.byte_offsets_pre_lut):
					raise Exception("Length of offsets %d != length of byte offsets passed in" % (len(self.offsets), len(self.byte_offsets_pre_lut)))
				
				for minor_frame_idx in self.byte_offsets.keys():
					for cnt, offset, col_idx, idx in self.byte_offsets[minor_frame_idx]:
						byte_offset_key = (minor_frame_idx, idx)
						
						if cnt >= len(self.offsets):
							raise Exception("Could not find original offset index %d after LUT applied of offsets: %s" % (cnt, self.offsets))
						
						offset = self.offsets[cnt]
						byte_offset_pre_lut = self.byte_offsets_pre_lut[cnt]
						
						if not isinstance(offset, list): offset = [offset]
						if not isinstance(byte_offset_pre_lut, list): byte_offset_pre_lut = [byte_offset_pre_lut]
						
						byte_offset = []
						for pre_lut in byte_offset_pre_lut:
							post_lut = self.lut([pre_lut])
							byte_offset += [post_lut]
						
						trigger = state.Trigger(MINOR_FRAME_KEY, byte_offset_key)
						if trigger in self.trigger_map.keys():
							raise Exception("Byte offset key %s already in trigger map: %s" % (byte_offset_key, self.trigger_map[trigger]))
						self.trigger_map[trigger] = (byte_offset, offset, byte_offset_pre_lut)
			
			else:
				raise Exception("Cannot build trigger map with offset type: '%s'" % (type(self.byte_offsets)))
		
		else:
			raise Exception("Cannot build trigger map with byte offset type: '%s'" % (type(self.byte_offsets)))
	def get_trigger_indices(self, *args, **kwds):
		return self.trigger_map.keys()
	def collect(self, byte, frame, minor_frame_idx, idx, trigger, *args, **kwds):	# FIXME: Data might be zero filled, use valid list
		#if isinstance(self.byte_offsets, list):	# Extract index if it applies to all minor frames
		#	trigger = state.Trigger(MINOR_FRAME_KEY, (trigger.indices[1],))
		
		res, map_res = trigger.check_map(self.trigger_map)
		
		#if trigger not in self.trigger_map.keys():
		if not res:
			raise Exception("Trigger %s not in trigger map: %s" % (trigger, self.trigger_map))
			return
		
		# There are two strategies:
		# 1) Treat byte offsets as only within the current frame (with list, or list of lists).
		# 2) The trigger index (the highest of the original offset list) marks the last byte offset that can be used (when dict).
		#    Need to search in current frame, and back through previous ones, to find next available byte offset.
		
		byte_offset, offset, byte_offset_pre_lut = map_res[0]	#self.trigger_map[trigger]
		
		if byte_offset_pre_lut is not None:	# byte_offset is now a list of dicts
			if not minor_frame_idx in byte_offset:
				raise Exception("Minor frame index %d not in byte offset map" % (minor_frame_idx))
			
			_byte_offset = byte_offset[minor_frame_idx]
			_byte_offset_idx = map(lambda x: x[3], _byte_offset).index(idx)
			mapped_byte_offsets = []
			
			max_minor_frame_idx = 0
			for _byte_offset in byte_offset:
				max_minor_frame_idx = max(max_minor_frame_idx, max(_byte_offset.keys()))
			
			for _byte_offset_pre_lut in byte_offset_pre_lut[::-1]:	# Looked up first element already
				search_minor_frame_idx = minor_frame_idx
				while True:
					search_minor_frame_idx -= 1
					if search_minor_frame_idx == minor_frame_idx:
						return
					if search_minor_frame_idx == -1: search_minor_frame_idx = max_minor_frame_idx
			
			mapped_byte_offsets = mapped_byte_offsets[::-1]
			
			return
		
		# list, list of lists, or dict with single item (i.e. all in same frame)
		l = []
		for i in byte_offset:	# FIXME: If -ve, get from previous frames
			l += [frame[i]]
		return l

class ByteOffset(ByteOffsetPrototype, ByteParser):
	def __init__(self, offsets, lut=None, *args, **kwds):
		ByteOffsetPrototype.__init__(self, offsets, lut=lut, *args, **kwds)
		ByteParser.__init__(self, *args, **kwds)

class BitOffset(ByteOffsetPrototype, BitParser):
	def __init__(self, offsets, lut=None, *args, **kwds):
		ByteOffsetPrototype.__init__(self, offsets, byte_offsets=utils.bits_to_bytes(offsets), lut=lut, *args, **kwds)
		BitParser.__init__(self, *args, **kwds)
	def collect(self, byte, frame, minor_frame_idx, idx, trigger, *args, **kwds):	# FIXME: Data might be zero filled, use valid list
		res = ByteOffsetPrototype.collect(self, byte, frame, minor_frame_idx, idx, trigger, *args, **kwds)
		if not isinstance(res, list):
			raise Exception("BitOffset: ByteOffsetPrototype collect returned: %s" % (res))
			return res
		
		#if isinstance(self.byte_offsets, list):	# Extract index if it applies to all minor frames
		#	trigger = state.Trigger(MINOR_FRAME_KEY, (trigger.indices[1],))
		
		res, map_res = trigger.check_map(self.trigger_map)
		
		byte_offset, offset, byte_offset_pre_lut = map_res[0]	#self.trigger_map[trigger]
		
		l = []
		for byte, i, j in zip(res, byte_offset, offset):
			if (j / 8) != i:
				raise Exception("Collecting invalid bit offset %d from byte offset %d (bit offset is byte %d)" % (j, i, (j/8)))
			bit_offset = j % 8
			bit = 0
			if (byte & (1<<(7-bit_offset))):
				bit = 1
			l += [bit]
		return l

class ModeFilteredByteOffset(CustomOffset, ByteParser):
	def __init__(self, offsets_map, default_mode=None, *args, **kwds):	# FIXME: lut
		CustomOffset.__init__(self, [state.FrameTracker])
		ByteParser.__init__(self, *args, **kwds)
		self.offsets = {}
		self.default_mode = default_mode
		for k in offsets_map.keys():
			self.offsets[k] = ByteOffset(offsets_map[k])
	def _get_mode(self, *args, **kwds):
		mode = self.default_mode
		if 'mode' in kwds.keys() and kwds['mode'] is not None:
			mode = kwds['mode']
		if mode is None:
			raise Exception("No mode given to ModeFilteredByteOffset")
		return mode
	def get_trigger_indices(self, *args, **kwds):
		return self.offsets[self._get_mode(*args, **kwds)].get_trigger_indices(*args, **kwds)
	def collect(self, *args, **kwds):
		return self.offsets[self._get_mode(*args, **kwds)].collect(*args, **kwds)

class SubcomByteOffsetPrototype(CustomOffset):
	def __init__(self, subcom_key, offsets, byte_offsets=None, auto_complete=True, *args, **kwds):
		CustomOffset.__init__(self, [state.SubcomTracker])
		self.subcom_key = subcom_key
		self.offsets = offsets
		self.byte_offsets = byte_offsets
		if auto_complete:
			self._complete_init(byte_offsets or offsets)
	def _complete_init(self, byte_offsets):
		self.byte_offsets = byte_offsets
		self.trigger_map = {}
		for byte_offset, offset in zip(byte_offsets, self.offsets):
			if isinstance(byte_offset, list):
				byte_offset_key = max(byte_offset)
			else:
				byte_offset_key = byte_offset
				byte_offset = [byte_offset]
			if not isinstance(offset, list): offset = [offset]
			trigger = state.Trigger(self.subcom_key, (byte_offset_key,))
			if trigger in self.trigger_map.keys():
				raise Exception("Byte offset key %d already in trigger map: %s" % (byte_offset_key, self.trigger_map[trigger]))
			self.trigger_map[trigger] = (byte_offset, offset)
	def is_compatible_tracker(self, c):
		if not CustomOffset.is_compatible_tracker(self, c): return False
		return c.can_handle_subcom(self.subcom_key)
	def get_trigger_indices(self, *args, **kwds):
		return self.trigger_map.keys()
	def collect(self, byte, frame, idx, trigger, *args, **kwds):	# FIXME: Data might be zero filled, use valid list
		if trigger not in self.trigger_map.keys():	# FIXME: Use trigger.check_map (will still work for now)
			raise Exception("Trigger %s not in trigger map: %s" % (trigger, self.trigger_map))
			return
		byte_offset, offset = self.trigger_map[trigger]
		l = []
		for i in byte_offset:
			l += [frame[i]]
		return l

class SubcomByteOffset(SubcomByteOffsetPrototype, ByteParser):
	def __init__(self, subcom_key, offsets, *args, **kwds):
		SubcomByteOffsetPrototype.__init__(self, subcom_key, offsets)
		ByteParser.__init__(self, *args, **kwds)

class SubcomBitOffset(SubcomByteOffsetPrototype, BitParser):
	def __init__(self, subcom_key, offsets, *args, **kwds):
		SubcomByteOffsetPrototype.__init__(self, subcom_key, offsets, utils.bits_to_bytes(offsets))
		BitParser.__init__(self, *args, **kwds)
	def collect(self, byte, frame, idx, trigger, *args, **kwds):	# FIXME: Data might be zero filled, use valid list
		res = SubcomByteOffsetPrototype.collect(self, byte, frame, idx, trigger, *args, **kwds)
		if not isinstance(res, list):
			raise Exception("SubcomBitOffset: SubcomByteOffsetPrototype collect returned: %s" % (res))
			return res
		
		byte_offset, offset = self.trigger_map[trigger]	# FIXME: Use trigger.check_map (will still work for now)
		
		l = []
		for i, byte, j in zip(byte_offset, res, offset):	# Keeping 'byte_offset' to enable offset check
			if (j / 8) != i:
				raise Exception("Collecting invalid bit offset %d from byte offset %d (bit offset is byte %d)" % (j, i, (j/8)))
			bit_offset = j % 8
			bit = 0
			if (byte & (1<<(7-bit_offset))):
				bit = 1
			l += [bit]
		return l

class Element():
	FLAG_NONE	= 0x00
	def __init__(self, id, category=None, name=None, desc=None, positions=None, parser=None, validator=None, formatter=None, unit=None, flags=FLAG_NONE):
		if not isinstance(id, str) or len(id) == 0:
			raise Exception("Invalid Elemenet ID: %s" % (id))
		
		# Short name (no restrictions, as yet)
		self._id = id
		
		# Category for grouping
		self._category = category
		
		# Human-readable name
		self._name = name
		
		# Description
		self._desc = desc
		
		# Offset of relevant data
		if positions is not None and (isinstance(positions, list) or isinstance(positions, dict)):
			positions = ByteOffset(positions)
		self._positions = positions or utils.find_subclass(CustomOffset, [parser, validator, formatter])
		if self._positions is None:
			raise Exception("Element '%s' must have a supplier of offsets" % (id))
		#print "%s: %s" % (id, self._positions.get_trigger_indices())
		
		# Parser takes raw data picked by 'positions' definition and assembles final value
		self._parser = parser or utils.find_subclass(Parser, [validator, formatter, positions])
		if self._parser is None:
			raise Exception("Element '%s' does not have a parser" % (id))
		
		# Validator takes final value and determines the values correctness/goodness
		self._validator = validator or utils.find_subclass(Validator, [parser, formatter, positions]) or Validator()
		
		# Formatter will determine how final value is printed
		self._formatter = formatter or utils.find_subclass(Formatter, [parser, validator, positions]) or Formatter()
		
		# Unit of value
		self._unit = unit
		
		# Flags
		self._flags = flags
	def id(self): return self._id
	def positions(self): return self._positions
	def parser(self): return self._parser
	def validator(self): return self._validator
	def formatter(self): return self._formatter
	def unit(self): return self._unit
	def flags(self): return self._flags
	def __str__(self): return self.id()

def main():
	return 0

if __name__ == '__main__':
	main()
