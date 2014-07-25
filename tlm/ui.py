#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  ui.py
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

# FIXME:
# * Update prediction (using detected bitrate from Network)
# * Colour
# * Handle when screen size isn't large enough (curses throws ERR)

import curses, datetime, math

import state
from constants import *
from primitives import *

class Layout():
	def __init__(self, name, ui):
		self.name = name
		self.ui = ui
		self.active = False
		self.y_offset = 0
	def draw(self, y):
		pass
	def deactivate(self):
		self.active = False
	def activate(self, y):
		self.y_offset = y
		self.active = True

class MinorFrameLayout(Layout):
	def __init__(self, *args, **kwds):
		Layout.__init__(self, *args, **kwds)
		self.deframer = self.ui.engine.deframer
		self.last_updated_idx = 0
		self.changed = False
		self.prev_frame_idx = 0
	def activate(self, y):
		self.ui.engine.register(EVENT_NEW_BYTE, self)
		# FIXME: Draw the frame thus far
		Layout.activate(self, y)
	def deactivate(self):
		self.ui.engine.unregister(EVENT_NEW_BYTE, self)
		Layout.deactivate(self)
	def __call__(self, *args, **kwds):
		if not self.active:
			self.changed = True
			raise Exception("MinorFrameLayout callback while not active")
			return
		
		stdscr = self.ui.scr
		byte = kwds['byte']
		frame = kwds['frame']
		if kwds['idx'] is None:
			frame_idx = len(frame) - 1
		else:
			frame_idx = kwds['idx']
		
		width = 16
		section_length = 8
		y_factor = 2
		
		prev_frame_idx = frame_idx - 1
		if prev_frame_idx == -1:
			prev_frame_idx = MINOR_FRAME_LEN - 1
		#if prev_frame_idx < len(frame):
		if True:	# FIXME: Being lazy here
			y = prev_frame_idx / width
			x = prev_frame_idx % width
			#stdscr.move(y + y_offset, x * section_length)
			#stdscr.addstr("%03d %02x " % (prev_frame_idx, frame[prev_frame_idx]))
			stdscr.move(y*y_factor + self.y_offset, x * section_length + 3)
			stdscr.addstr(" ")
			stdscr.move(y*y_factor + self.y_offset, x * section_length + 3 + 3)
			stdscr.addstr(" ")
		
		y = frame_idx / width
		x = frame_idx % width
		stdscr.move(y*y_factor + self.y_offset, x * section_length)
		stdscr.addstr("%03d[%02x]" % (frame_idx, byte))
	def draw(self, y):
		#if not self.changed:
		#	return
		#self.deframer
		pass	# Purely event driven at the moment

class SubcomSubLayout():
	def __init__(self, key, subcom_tracker, y_offset):
		self.key = key
		self.subcom_tracker = subcom_tracker
		self.last_updated_idx = None
		self.y_offset = y_offset
	def name(self): return self.key

class SubcomLayout(Layout):
	def __init__(self, *args, **kwds):
		Layout.__init__(self, *args, **kwds)
		self.subcom_trackers = self.ui.engine.subcom_trackers
		self.subcom_sublayouts = {}
		
		self.width = 16
		self.y_factor = 2
		self.max_name_len = 0
		
		y = 0
		for subcom_key in self.subcom_trackers.keys():
			subcom_tracker = self.subcom_trackers[subcom_key]
			sublayout = SubcomSubLayout(subcom_key, subcom_tracker, y)
			self.max_name_len = max(self.max_name_len, len(sublayout.name()))
			self.subcom_sublayouts[subcom_key] = sublayout
			height = int(math.ceil(1.*subcom_tracker.length / self.width)) * self.y_factor - (self.y_factor - 1)
			y += (height + 3)
		
		self.x_offset = self.max_name_len + 4	# Additional space
		
		self.changed = False
	def draw(self, y):
		scr = self.ui.scr
		
		for subcom_key in self.subcom_trackers.keys():
			subcom_tracker = self.subcom_trackers[subcom_key]
			subcom_sublayout = self.subcom_sublayouts[subcom_key]
			scr.move(y + subcom_sublayout.y_offset + 2, 1)
			scr.addstr("%03d" % (subcom_tracker.discontinuity_cnt))
	def activate(self, y):
		for subcom_key in self.subcom_trackers.keys():
			self.subcom_trackers[subcom_key].register(EVENT_NEW_BYTE, self)
		
		scr = self.ui.scr
		
		for subcom_key in self.subcom_sublayouts.keys():
			subcom_sublayout = self.subcom_sublayouts[subcom_key]
			scr.move(y + subcom_sublayout.y_offset, 1)
			scr.addstr(subcom_sublayout.name())
		
		# FIXME: Draw the frame thus far
		
		Layout.activate(self, y)
	def deactivate(self):
		for subcom_key in self.subcom_trackers.keys():
			self.subcom_trackers[subcom_key].unregister(EVENT_NEW_BYTE, self)
		
		Layout.deactivate(self)
	def __call__(self, event, source, *args, **kwds):
		if not self.active:
			self.changed = True
			raise Exception("SubcomLayout callback while not active")
			return
		
		stdscr = self.ui.scr
		byte = kwds['byte']
		frame = kwds['frame']
		frame_idx = len(frame) - 1
		
		sublayout = self.subcom_sublayouts[source.key]
		
		section_length = 8
		
		prev_frame_idx = frame_idx - 1
		if prev_frame_idx == -1:
			prev_frame_idx = sublayout.subcom_tracker.length - 1
		#if prev_frame_idx < len(frame):
		if True:	# FIXME: Being lazy here
			y = prev_frame_idx / self.width
			x = prev_frame_idx % self.width
			stdscr.move(y*self.y_factor + self.y_offset + sublayout.y_offset, self.x_offset + x * section_length + 3)
			stdscr.addstr(" ")
			stdscr.move(y*self.y_factor + self.y_offset + sublayout.y_offset, self.x_offset + x * section_length + 3 + 3)
			stdscr.addstr(" ")
		
		y = frame_idx / self.width
		x = frame_idx % self.width
		stdscr.move(self.y_offset + sublayout.y_offset + y*self.y_factor, self.x_offset + x * section_length)
		stdscr.addstr("%03d[%02x]" % (frame_idx, byte))

class ElementsLayout(Layout):
	def __init__(self, elements, padding=10, *args, **kwds):
		Layout.__init__(self, *args, **kwds)
		self.elements = elements
		self.max_id_len = 0
		self.y_offset_map = {}
		self.trigger_map = {}
		self.padding = padding
		self.last_draw_time = {}
		self.draw_count = {}
		self.draw_time_delta = datetime.timedelta(milliseconds=250)
		self.max_value_len = 0
		self.full_refresh = False
		for element in self.elements:
			self.last_draw_time[element.id()] = None
			self.draw_count[element.id()] = 0
			self.max_id_len = max(self.max_id_len, len(element.id()))
			trigger_indices = self.ui.engine.get_element_state(element).get_element().positions().get_trigger_indices()
			for trigger_index in trigger_indices:
				if trigger_index not in self.trigger_map.keys(): self.trigger_map[trigger_index] = []
				self.trigger_map[trigger_index] += [element]
	def activate(self, y):
		scr = self.ui.scr
		cnt = 0
		self.y_offset_map = {}
		for element in self.elements:
			self.y_offset_map[element.id()] = y+cnt
			
			self.ui.engine.track(element.positions().get_trigger_indices(), self)
			
			scr.move(self.y_offset_map[element.id()], 1)
			scr.addstr(element.id())
			
			self.draw_element(element)
			
			cnt += 1
		
		Layout.activate(self, y)
	def deactivate(self):
		for element in self.elements:
			self.ui.engine.untrack(element.positions().get_trigger_indices(), self)
		
		Layout.deactivate(self)
	def __call__(self, *args, **kwds):
		trigger = kwds['trigger']
		res, map_res = trigger.check_map(self.trigger_map)
		
		if not res:
			raise Exception("%s not in %s" % (trigger, self.trigger_map.keys()))
		
		triggered_elements = map_res
		
		for element in triggered_elements:
			self.draw_element(element)
	def draw_element(self, element):
		scr = self.ui.scr
		element_state = self.ui.engine.get_element_state(element)
		scr.move(self.y_offset_map[element.id()], 1 + self.max_id_len + self.padding)
		scr.clrtoeol()
		
		if element_state.last_value is None:
			return
		
		self.draw_count[element.id()] += 1
		
		count_str = "[%04d]" % element_state.update_count
		scr.addstr(count_str)
		
		s = " = "
		value_str = element.formatter().format(element_state.last_value)
		s += value_str
		if element.unit() is not None and len(element.unit()) > 0:
			s += " " + element.unit()
		if element_state.last_valid is not None:
			if element_state.last_valid == True:
				s += " (valid)"	# FIXME: Green
			elif element_state.last_valid == False:
				s += " (invalid)"	# FIXME: Red
		if len(s) > self.max_value_len:
			self.max_value_len = len(s)
			self.full_refresh = True
		scr.addstr(s)
		
		if element_state.previous_value is not None:
			scr.move(self.y_offset_map[element.id()], 1 + self.max_id_len + self.padding + self.max_value_len + 10)	# MAGIC
			s = " (%03d: %s)" % ((self.ui.engine.get_local_time_now() - element_state.previous_value_time).total_seconds(), element.formatter().format(element_state.previous_value))
			scr.addstr(s)
		
		time_delta = self.ui.engine.get_local_time_now() - element_state.last_update_time
		time_str = "%03d" % time_delta.total_seconds()
		scr.move(self.y_offset_map[element.id()], self.ui.max_x - len(time_str))
		scr.addstr(time_str)
		
		trigger_str = str(element_state.last_trigger)
		scr.move(self.y_offset_map[element.id()], self.ui.max_x - len(time_str) - 3 - len(trigger_str))
		scr.addstr(trigger_str)
		
		self.last_draw_time[element.id()] = self.ui.engine.get_local_time_now()
	def draw(self, y_offset):
		for element in self.elements:
			if not self.full_refresh and self.last_draw_time[element.id()] is not None and (self.ui.engine.get_local_time_now() - self.last_draw_time[element.id()]) < self.draw_time_delta:
				return
			self.draw_element(element)
		self.full_refresh = False

class HistoryLayout(Layout):
	def __init__(self, width, elements, *args, **kwds):
		Layout.__init__(self, *args, **kwds)
		self.trigger_map = {}
		self.history_map = {}
		self.elements = elements
		self.history_lengths = {}
		self.width = width
		
		for spec in elements:
			element, history_length = spec
			self.history_lengths[element] = history_length
			self.history_map[element] = []
			trigger_indices = self.ui.engine.get_element_state(element).get_element().positions().get_trigger_indices()
			self.ui.engine.track(trigger_indices, self)
			for trigger_index in trigger_indices:
				if trigger_index not in self.trigger_map.keys(): self.trigger_map[trigger_index] = []
				self.trigger_map[trigger_index] += [element]
		
		self.changed = False
	def __call__(self, *args, **kwds):
		self.changed = True
		
		trigger = kwds['trigger']
		
		res, map_res = trigger.check_map(self.trigger_map)
		
		if not res:
			raise Exception("%s not in %s" % (trigger, self.trigger_map.keys()))
		
		triggered_elements = map_res
		
		for element in triggered_elements:
			element_state = self.ui.engine.get_element_state(element)
			
			if element_state.last_value is None:
				return
			
			value_str = element_state.get_element().formatter().format(element_state.last_value)
			
			history = self.history_map[element]
			history += [value_str]
			diff = len(history) - self.history_lengths[element]
			if diff > 0:
				self.history_map[element] = history[diff:]
	def draw(self, y):
		if not self.changed:
			return
		
		scr = self.ui.scr
		
		x = 8
		n = 0
		for spec in self.elements:
			element, history_length = spec
			history = self.history_map[element]
			
			cnt = 0
			
			scr.move(y + cnt, x)
			scr.addstr(element)
			
			cnt += 2
			
			for val in history:
				if n == 0:
					scr.move(y + cnt, 0)
					scr.clrtoeol()
				
				scr.move(y + cnt, x)
				scr.addstr(val)
				cnt += 1
			
			x += self.width
			n += 1

class UserInterface():
	def __init__(self, engine, timeout=10):
		self.engine = engine
		self.timeout = timeout
		
		self.scr = None
		self.active_layout = None
		self.max_y, self.max_x = 0, 0
		
		self.log_message = ""
		self.update_log_message = False
		
		self.last_engine_state = state.STATE_NONE
		self.last_active_layout_name = ""
		
		self.element_layout_key_shortcuts = {}
		self.element_layouts = []
		
		self.layout_y_offset = 5
	def start(self, element_layouts):
		self.minor_frame_layout = MinorFrameLayout("raw", self)
		self.element_layout_key_shortcuts['`'] = self.minor_frame_layout
		self.subcom_layout = SubcomLayout("subcom", self)
		self.element_layout_key_shortcuts['~'] = self.subcom_layout
		
		print "Building history layout..."
		history_length = 40
		self.history_layout = HistoryLayout(name="history", ui=self, width=24, elements=[
			('hps_1_temp_supercom', history_length),
			('hps_2_temp_supercom', history_length),
			('hps_1_tc', history_length),
			#('hps_1_tcX', history_length),
			('hps_2_tc', history_length),
			#('hps_2_tcX', history_length),
			('accelerometer', history_length),
		])	# MAGIC
		self.element_layout_key_shortcuts['h'] = self.history_layout
		
		print "Building layouts..."
		for element_layout in element_layouts:
			name = element_layout[0]
			shortcut = name[0]
			if len(element_layout) >= 3:
				shortcut = element_layout[2]
			elements = []
			for element_name in element_layout[1]:
				element = self.engine.get_element(element_name, safe=False)
				if element is None:
					print "The element '%s' was not found for layout '%s'" % (element_name, name)
				element = self.engine.get_element(element_name)
				elements += [element]
			layout = ElementsLayout(elements, name=name, ui=self)
			self.element_layouts += [layout]
			if shortcut not in self.element_layout_key_shortcuts.keys():
				self.element_layout_key_shortcuts[shortcut] = layout
			else:
				print "ElementLayout '%s' already has shortcut key '%s'" % (self.element_layout_key_shortcuts[shortcut].name, shortcut)
		
		self.scr = curses.initscr()
		#curses.start_color()	# FIXME
		self.scr.timeout(self.timeout)	# -1 for blocking
		self.scr.keypad(1)	# Otherwise app will end when pressing arrow keys
		
		#curses.raw()
		#curses.noecho()
		#curses.cbreak()
		#curses.nl / curses.nonl
		#self.scr.deleteln()
		
		self.switch_layout(self.minor_frame_layout)
		self.update()
		
		#self.scr.refresh()	# Done in 'update'
	def run(self):
		if not self.handle_keys():
			return False
		
		self.update()
		
		return True
	def log(self, msg):
		self.log_message = msg
		self.update_log_message = True
	def refresh_screen_state(self):
		self.max_y, self.max_x = self.scr.getmaxyx()
	def update(self):
		self.refresh_screen_state()
		
		if self.last_engine_state != self.engine.get_state():
			self.scr.move(self.max_y-1, 0)
			self.scr.clrtoeol()
			self.scr.addstr(state.STATE_TXT[self.engine.get_state()])
			self.last_engine_state = self.engine.get_state()
		
		if True:
			self.scr.move(0, 0)
			#self.scr.clrtoeol()	# Don't since current layout name is on RHS
			self.scr.addstr("Current time: %s" % (self.engine.get_local_time_now()))
		
		if self.engine.net.last_enqueue_time:
			self.scr.move(1, 0)
			#self.scr.clrtoeol()	# Don't since layout shortcuts are on RHS
			self.scr.addstr("Data arrived: %s" % (self.engine.net.last_enqueue_time))
		
		if True:
			self.scr.move(2, 0)
			self.scr.clrtoeol()
			self.scr.addstr("Data lag    : %+f" % (self.engine.net.get_time_diff().total_seconds()))
			self.scr.move(2, 32)
			self.scr.addstr("Data source: %s" % (self.engine.net.get_status_string()))
			
			self.scr.move(3, 0)
			self.scr.clrtoeol()
			self.scr.addstr("Complete frame count: %d, sync reset count: %d, minor frame discontinuities: %d, minor frame index lock: %s, auto minor frame index: %s" % (
				self.engine.deframer.get_complete_frame_count(),
				self.engine.deframer.get_sync_reset_count(),
				self.engine.frame_tracker.frame_discontinuity_cnt,
				self.engine.frame_tracker.ignore_minor_frame_idx,
				self.engine.frame_tracker.minor_frame_idx,
			))
		
		if self.update_log_message:
			self.scr.move(self.max_y-2, 0)
			self.scr.clrtoeol()
			self.scr.addstr(self.log_message)
			self.update_log_message = False
		
		if self.active_layout:
			if self.last_active_layout_name != self.active_layout.name:
				# Screen should have been cleared when changing layout
				self.scr.move(0, self.max_x - len(self.active_layout.name))
				self.scr.addstr(self.active_layout.name)
				self.last_active_layout_name = self.active_layout.name
			
			self.active_layout.draw(self.layout_y_offset)
		
		self.scr.refresh()
	def draw_underlay(self):
		shortcuts = "".join(self.element_layout_key_shortcuts.keys())
		self.scr.move(1, self.max_x - len(shortcuts))
		self.scr.addstr(shortcuts)
	def switch_layout(self, layout, erase=True):
		if self.active_layout:
			self.active_layout.deactivate()
		
		if erase:
			self.scr.erase()
			self.last_engine_state = None
			self.last_active_layout_name = ""
		
		self.refresh_screen_state()
		
		self.draw_underlay()
		
		self.active_layout = layout
		self.active_layout.activate(self.layout_y_offset)
	def handle_keys(self):
		ch = self.scr.getch()
		if ch > -1:
			if ch == 27:	# ESC (quit)
				return False
			elif ch >= ord('0') and ch <= ord('9'):
				idx = (ch - ord('0') - 1) % 10
				if idx < len(self.element_layouts):
					self.switch_layout(self.element_layouts[idx])
			elif ch >= 0 and ch < 256 and chr(ch) in self.element_layout_key_shortcuts.keys():
				self.switch_layout(self.element_layout_key_shortcuts[chr(ch)])
			else:
				self.scr.move(self.max_y-3, 0)
				self.scr.clrtoeol()
				self.scr.addstr(str(ch))
		return True
	def stop(self):
		if not self.scr:
			return
		
		self.scr.erase()
		self.scr.refresh()
		
		curses.nocbreak()
		self.scr.keypad(0)
		curses.echo()
		curses.endwin()

def main():
	return 0

if __name__ == '__main__':
	main()
