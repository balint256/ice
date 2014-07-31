#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  state.py
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

from constants import *

# Engine states
STATE_NONE = 0
STATE_WAITING_FOR_SYNC = 1
STATE_RECEIVING = 2

STATE_TXT = {
	STATE_NONE:				'None',
	STATE_WAITING_FOR_SYNC:	'Waiting for sync',
	STATE_RECEIVING:		'Receiving'
}

class ElementState():
	def __init__(self, element, manager, engine):
		self.element = element
		self.manager = manager
		self.engine = engine
		
		self.last_update_time = None
		self.last_value = None
		self.previous_value = None
		self.previous_value_time = None
		self.last_valid = None
		self.last_trigger = None
		self.update_count = 0
	def get_element(self): return self.element
	def _update(self, time, trigger, res, valid):
		self.last_update_time = time
		self.update_count += 1
		
		if res is not None and res != self.last_value:
			self.previous_value = self.last_value
			self.previous_value_time = time
		
		self.last_trigger = trigger
		self.last_value = res
		self.last_valid = valid
	def __call__(self, trigger, *args, **kwds):
		#try:
			#if self.element.id() == ?: raise Exception("%s" % (self.element.id()))	# TEST
			
			local_time_now = self.manager.engine.get_local_time_now()
			
			raw_data = self.element.positions().collect(trigger=trigger, state=self, mode=self.engine.options.mode, *args, **kwds)
			
			(res, val) = self.element.parser().parse(raw_data, element=self.element, state=self, *args, **kwds)
			if res == False:
				return False	# [This will cause the callback chain to abort] Not any more
			
			#if self.element.id() == ?: raise Exception("%s" % (self.element.id()))	# TEST
			
			valid = self.element.validator().validate(val, state=self)
			
			self._update(local_time_now, trigger, val, valid)
		#except Exception, e:
		#	self.last_value = str(e)
		#	raise e

class EventDispatcher():
	def __init__(self, events):
		self.events = events
		self.listeners = {}
		for e in events: self.listeners[e] = []
	def register(self, event, target):
		if event not in self.events:
			raise Exception("Unknown event: '%s'" % (event))
		if target in self.listeners[event]:
			return False
		self.listeners[event] += [target]
		return True
	def unregister(self, event, target):
		if event not in self.events:
			raise Exception("Unknown event: '%s'" % (event))
		if target not in self.listeners[event]:
			return False
		self.listeners[event].remove(target)
		return True
	def dispatch(self, event, *args, **kwds):
		if event not in self.listeners.keys():
			return None
		for target in self.listeners[event]:
			if target(event=event, source=self, *args, **kwds) == False:
				return False
		return True

class Tracker():	# FIXME: Can turn this into an EventDispatcher as long as indices as hashable (tuples are)
	#def __init__(self, compatible_targets, *args, **kwds):
	#	self.compatible_targets = compatible_targets
	#def is_compatible_target(self, c):
	#	return issubclass(c.__class__, tuple(self.compatible_targets))
	def track(self, indices, target):
		raise Exception("Implement Tracker track")
	def untrack(self, indices, target):
		raise Exception("Implement Tracker untrack")

class Trigger():
	def __init__(self, name, indices):
		self.name = name
		if not isinstance(indices, tuple):
			raise Exception("Trigger indices must be a tuple: %s" % (str(indices)))
		self.indices = indices
		self.hash_cache = str(self).__hash__()
	def __str__(self):
		return "%s:%s" % (self.name, ",".join(map(str, self.indices)))
	def __repr__(self):
		return str(self)
	def __hash__(self):
		return self.hash_cache
	def __eq__(self, other):
		return str(self.name) == str(other.name) and self.indices == other.indices
	def check_map(self, m):
		if self not in m.keys():
			return (False, None)
		v = m[self]
		if not isinstance(v, list): v = [v]
		return (True, v)

class MinorFrameTrigger(Trigger):
	def __init__(self, *args, **kwds):
		Trigger.__init__(self, *args, **kwds)
	def check_map(self, m):
		l = None
		if self in m.keys():
			v = m[self]
			if not isinstance(v, list): v = [v]
			l = v
		all_minor_frames = Trigger(self.name, (self.indices[1],))
		if all_minor_frames in m.keys():
			if l is None: l = []
			v = m[all_minor_frames]
			if not isinstance(v, list): v = [v]
			l += v
		if l is None:
			return (False, None)
		return (True, l)

class SubcomTracker(Tracker, EventDispatcher):	# FIXME: , CustomOffset
	def __init__(self, key, length, offsets, major_length):
		if offsets != sorted(offsets):
			raise Exception("Offsets supplied to SubcomTracker for '%s' not in order: %s" % (key, offsets))
		#Tracker.__init__(self, [SubcomByteOffset, SubcomBitOffset])
		EventDispatcher.__init__(self, [EVENT_NEW_BYTE, EVENT_NEW_FRAME])
		self.key = key
		self.length = length
		self.offsets = offsets
		self.major_length = major_length
		self.update_map = {}
		
		self.reset()
		
		self._build_indices()
	def reset(self):
		self.subcom_frame = []
		self.last_subcom_frame = []
		self.discontinuity_cnt = 0
	def _build_indices(self):
		self.trigger_indices = []
		self.offset_map = {}
		cnt = 0
		for i in range(self.major_length):
			self.offset_map[i] = []
			for o in self.offsets:
				self.trigger_indices += [Trigger(MINOR_FRAME_KEY, (i, o))]
				self.offset_map[i] += [cnt]
				cnt = (cnt + 1) % self.length
		if cnt != 0:
			raise Exception("Subcom '%s' index count ended on %d" % (self.key, cnt))
	def get_subcom_key(self): return self.key
	def can_handle_subcom(self, key):
		return (self.get_subcom_key() == key)
	def get_trigger_indices(self): return self.trigger_indices	# FIXME: , *args, **kwds (for CustomOffset)
	def update(self, byte, frame, minor_frame_idx, idx, trigger, *args, **kwds):
		minor_frame_offset_index = self.offsets.index(idx)
		subcom_offset_list = self.offset_map[minor_frame_idx]
		subcom_offset = subcom_offset_list[minor_frame_offset_index]
		
		diff = subcom_offset - len(self.subcom_frame)
		
		if diff < 0:
			self.discontinuity_cnt += 1
			self.subcom_frame = [0]*subcom_offset
		elif diff > 0:
			if len(self.subcom_frame) == 0:	# Starting a new stream, so discontinuity is OK
				pass
			else:
				self.discontinuity_cnt += 1
			self.subcom_frame += [0]*diff
		
		self.subcom_frame += [byte]
		
		self.dispatch(EVENT_NEW_BYTE, byte=byte, frame=self.subcom_frame)
		
		idx = len(self.subcom_frame) - 1
		
		if idx in self.update_map.keys():
			targets = self.update_map[idx]
			trigger = Trigger(self.key, (idx,))
			#if self.key == ? and idx == ?: raise Exception("%s[%d]: %s" % (self.key, idx, map(lambda x: x.element.id(), targets)))	# TEST
			for target in targets:
				res = target(byte=byte, frame=self.subcom_frame, idx=idx, trigger=trigger)
				#if res == False:
				#	break
		
		if len(self.subcom_frame) == self.length:	# Complete
			self.dispatch(EVENT_NEW_FRAME, frame=self.subcom_frame)	# Trigger before last frame is overwritten
			self.last_subcom_frame = self.subcom_frame
			self.subcom_frame = []
	def track(self, indices, target):
		for index in indices:
			#assert(index.name in ALL_SUBCOM_LIST)	# FIXME
			index, = index.indices
			if index < 0 or index >= self.length:
				raise Exception("Unable to track index %d outside of SubcomTracker length %d" % (index, self.length))
			if index not in self.update_map.keys():
				self.update_map[index] = []
			if target not in self.update_map[index]:
				self.update_map[index] += [target]
		#return indices
	def untrack(self, indices, target):
		for index in indices:
			#assert(index.name in ALL_SUBCOM_LIST)	# FIXME
			index, = index.indices
			if index not in self.update_map.keys():
				continue
			if target not in self.update_map[index]:
				continue
			self.update_map[index].remove(target)
		#return indices

class FrameTracker(Tracker, EventDispatcher):
	def __init__(self, length):
		#Tracker.__init__(self, [ByteOffset, BitOffset])
		EventDispatcher.__init__(self, [EVENT_NEW_BYTE, EVENT_NEW_FRAME])
		self.length = length
		
		self.continuous_minor_frame_idx_increment_limit = 3	# MAGIC
		self.ignored_continuous_minor_frame_idx_increment_limit = 3	# MAGIC
		
		self.major_frame_update_map = {}
		
		self.reset()
	def reset(self, resync=False):
		self.last_frame = None
		self.last_byte = None
		self.minor_frame_idx = None
		self.major_frame_map = {}
		self.continuous_minor_frame_idx_increment_cnt = 0
		self.ignore_minor_frame_idx = False
		self.last_ignored_minor_frame_idx = None
		self.ignored_continuous_minor_frame_idx_increment_cnt = 0
		
		if resync:
			return
		
		self.frame_discontinuity_cnt = 0
	def update(self, byte, frame, sync=False, idx=None, internal=False, *args, **kwds):
		if idx is not None and idx >= len(frame):
			raise Exception("FrameTracker: manual byte index is %d, but length of frame is %d" % (idx, len(frame)))
		
		if sync:
			self.reset(True)	# Framer was reset, so reset local tracking state
		
		manually_set_minor_frame_idx = False
		
		# FIXME: This assumes complete frames (could do more clever tracking)
		if idx == 0 and len(frame) > MINOR_FRAME_IDX_OFFSET and self.minor_frame_idx != frame[MINOR_FRAME_IDX_OFFSET]:
			if self.minor_frame_idx is not None and frame[MINOR_FRAME_IDX_OFFSET] != ((self.minor_frame_idx + 1) % self.length):
				self.frame_discontinuity_cnt += 1
			self.minor_frame_idx = frame[MINOR_FRAME_IDX_OFFSET]
			manually_set_minor_frame_idx = True
		
		if self.last_frame is not None and len(self.last_frame) == MINOR_FRAME_LEN:	# Last frame is complete
			if idx is None:
				if len(frame) != 1:
					raise Exception("Invalid state in FrameTracker: last frame appears complete but new byte's frame has length %d" % (len(frame)))
			
			if manually_set_minor_frame_idx == False:
				self.minor_frame_idx = (self.minor_frame_idx + 1) % self.length	# Last frame is complete, auto-increment for the new one
		
		if idx is None:
			idx = len(frame) - 1
		
		# This will still get run when at MINOR_FRAME_IDX_OFFSET
		if manually_set_minor_frame_idx == False and idx == MINOR_FRAME_IDX_OFFSET:
			if self.minor_frame_idx is not None:
				if frame[idx] != self.minor_frame_idx:
					self.frame_discontinuity_cnt += 1
					if not self.ignore_minor_frame_idx:
						# Force update
						#self.last_frame = None
						self.minor_frame_idx = None
					else:
						if self.last_ignored_minor_frame_idx is not None and frame[idx] == ((self.last_ignored_minor_frame_idx + 1) % self.length):
							self.ignored_continuous_minor_frame_idx_increment_cnt += 1
							if self.ignored_continuous_minor_frame_idx_increment_cnt == self.ignored_continuous_minor_frame_idx_increment_limit:
								self.minor_frame_idx = None
								self.ignore_minor_frame_idx = False
								self.continuous_minor_frame_idx_increment_cnt = 0
						self.last_ignored_minor_frame_idx = frame[idx]
				else:
					self.continuous_minor_frame_idx_increment_cnt += 1
					if self.continuous_minor_frame_idx_increment_cnt == self.continuous_minor_frame_idx_increment_limit:
						self.ignore_minor_frame_idx = True
					self.last_ignored_minor_frame_idx = None
					self.ignored_continuous_minor_frame_idx_increment_cnt = 0
			
			#if self.last_frame is None:
			if self.minor_frame_idx is None:
				self.minor_frame_idx = frame[idx]	# Update now
				
				for i in range(idx):
					self.update(frame[i], frame[:i+1], internal=True)	# FIXME: Check expectation of last_byte/last_frame updating below
			else:
				if not self.ignore_minor_frame_idx:
					self.minor_frame_idx = frame[idx]
		
		if self.minor_frame_idx is not None:
			self.major_frame_map[self.minor_frame_idx] = frame
			
			self.dispatch(event=EVENT_NEW_BYTE, byte=byte, frame=frame, minor_frame_idx=self.minor_frame_idx, idx=idx)
			
			if self.minor_frame_idx in self.major_frame_update_map.keys():
				minor_frame_update_map = self.major_frame_update_map[self.minor_frame_idx]
				
				if idx in minor_frame_update_map.keys():
					targets = minor_frame_update_map[idx]
					trigger = MinorFrameTrigger(MINOR_FRAME_KEY, (self.minor_frame_idx, idx))
					for target in targets:
						res = target(byte=byte, frame=frame, minor_frame_idx=self.minor_frame_idx, idx=idx, trigger=trigger)
						#if res == False:
						#	break
			
			self.dispatch(event=EVENT_NEW_FRAME, frame=frame, minor_frame_idx=self.minor_frame_idx)
		
		# These are updated *after* the event handlers are called
		#if internal == False:
		if True:	# Will always update (even when doing catch-up)
			self.last_byte = byte
			self.last_frame = list(frame[:idx+1])	# Make a copy
	def track(self, indices, target):
		#l = []
		for index in indices:
			assert(index.name == MINOR_FRAME_KEY)
			index = index.indices
			assert(isinstance(index, tuple) and len(index) > 0)
			if len(index) != 2:
				index = index[0]
				for i in range(self.length):
					#l += 
					self._track([(i, index)], target)
			else:
				assert(len(index) == 2)
				#l += 
				self._track([index], target)
		#return l
	def _track(self, indices, target):
		#l = []
		for minor_idx, frame_idx in indices:
			if minor_idx < 0 or minor_idx >= self.length:
				raise Exception("Unable to track index %d outside of FrameTracker length %d" % (minor_idx, self.length))
			#l += [Trigger(MINOR_FRAME_KEY, (minor_idx, frame_idx))]
			if minor_idx not in self.major_frame_update_map.keys():
				self.major_frame_update_map[minor_idx] = {}
			minor_frame_update_map = self.major_frame_update_map[minor_idx]
			if frame_idx not in minor_frame_update_map.keys():
				minor_frame_update_map[frame_idx] = []
			if target in minor_frame_update_map[frame_idx]:
				continue
			minor_frame_update_map[frame_idx] += [target]
		#return l
	def untrack(self, indices, target):
		#l = []
		for index in indices:
			assert(index.name == MINOR_FRAME_KEY)
			index = index.indices
			assert(isinstance(index, tuple) and len(index) > 0)
			if len(index) != 2:
				index = index[0]
				for i in range(self.length):
					#l += 
					self._untrack([(i, index)], target)
			else:
				assert(len(index) == 2)
				#l += 
				self._untrack([index], target)
		#return l
	def _untrack(self, indices, target):
		#l = []
		for minor_idx, frame_idx in indices:
			#l += [Trigger(MINOR_FRAME_KEY, (minor_idx, frame_idx))]
			if minor_idx not in self.major_frame_update_map.keys():
				continue
			minor_frame_update_map = self.major_frame_update_map[minor_idx]
			if frame_idx not in minor_frame_update_map.keys():
				continue
			if target not in minor_frame_update_map[frame_idx]:
				continue
			minor_frame_update_map[frame_idx].remove(target)
		#return l

def main():
	return 0

if __name__ == '__main__':
	main()
