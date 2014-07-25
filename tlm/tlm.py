#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  tlm.py
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

import sys, socket, traceback, os, sys, datetime, time

from optparse import OptionParser

import ui, net, state, res, server
from constants import *
from primitives import *

_layouts = None
try:
	import layout
	_layouts = layout.get_layouts()
except:
	print "Failed to import layout - will auto-generate"

def _global_log(msg):
	print "%s: %s" % (datetime.datetime.now(), msg)

global_log_fn = _global_log

def global_log(msg):
	global_log_fn(msg)

class Deframer():
	def __init__(self, length):
		self.length = length
		self.complete_frame_cnt = 0
		self.sync_reset_cnt = 0
	def get_complete_frame_count(self): return self.complete_frame_cnt
	def get_sync_reset_count(self): return self.sync_reset_cnt
	def get_state(self):
		return state.STATE_NONE
	def process(self, buffers, accept_fn=None):
		pass

class ByteDeframer(Deframer):
	def __init__(self, length):
		Deframer.__init__(self, length)
		self.synced = False
		self.sync_word = 0x12fc819fbe
		self.sync_word_length = 5
	def get_state(self):
		if self.synced: return state.STATE_RECEIVING
		return state.STATE_WAITING_FOR_SYNC
	def process(self, buffers, accept_fn=None):
		for buf in buffers:
			if buf.get_flags() & net.NetworkBuffer.FLAG_DROP:
				self.synced = False
			
			resync = False
			if buf.get_flags() & net.NetworkBuffer.FLAG_FIRST:
				resync = True
			
			data = map(ord, buf.get_buffer())	# Each buffer should be a complete frame
			
			if len(data) != self.length:
				self.synced = False
				self.sync_reset_cnt += 1
				continue
			
			sync_parts = data[self.length-self.sync_word_length:]
			sync_word = 0
			for b in sync_parts:
				sync_word <<= 8
				sync_word |= b
			if sync_word == self.sync_word:
				self.synced = True
			else:
				self.synced = False
				continue
			
			idx = 0
			for b in data:
				if accept_fn:
					accept_fn(b, data, resync, idx)
				idx += 1
			
			self.complete_frame_cnt += 1

class SymbolDeframer(Deframer):
	def __init__(self, length):
		Deframer.__init__(self, length)
		self.synced = False
		self.skip = 0
		self.last_sym = None
		self.sym_idx = 0
		self.byte = 0
		self.bit_idx = 0
		self.sym_cnt = 2
		self.frame = []
		self.pre_sync_byte = 0xbe >> 1	# Last byte of sync without last bit
		self.newly_synced = False
	def get_state(self):
		if self.synced: return state.STATE_RECEIVING
		return state.STATE_WAITING_FOR_SYNC
	def process(self, buffers, accept_fn=None):
		for buf in buffers:
			if buf.get_flags() & net.NetworkBuffer.FLAG_DROP:
				self.synced = False
				self.skip = 0
			
			data = map(ord, buf.get_buffer())
			cnt = 0
			for b in data:
				cnt += 1
				if self.skip > 0:
					self.skip -= 1
					continue
				
				if (b & 0x2) == 0x2:	# Correlated
					self.sym_idx = 0
					
					if self.synced:
						diff = (self.length - 1) - len(self.frame)
						if diff > 0 or self.byte != self.pre_sync_byte:	# If not in the final byte, then something has gone wrong
							#raise Exception("Sync byte diff: %d, %02x != %02x" % (diff, self.byte, self.pre_sync_byte))	# TEST
							self.sync_reset_cnt += 1
							self.synced = False
					
					if self.synced == False:
						self.synced = True
						self.skip = 1	# Flag on first bit after access code
						self.bit_idx = 0
						self.byte = 0
						self.frame = []
						self.newly_synced = True
						continue
					else:	# In the final byte
						self.byte = self.pre_sync_byte
						self.bit_idx = 7
						#if diff > 0:
						#	self.frame += ([0] * diff)	# Can no longer get here
				
				if self.synced == False:
					continue
				
				b &= 0x1
				
				if self.sym_idx != (self.sym_cnt-1):
					self.last_sym = b
					self.sym_idx += 1
					continue
				
				self.sym_idx = 0
				
				qli = self.last_sym ^ (~b & 0x1)	# d1 ^ (not d2)
				
				self.byte <<= 1
				self.byte |= qli
				self.bit_idx += 1
				
				if self.bit_idx == 8:
					self.frame += [self.byte]
					
					if len(self.frame) > self.length:
						raise Exception("Invalid frame length: %d" % (len(self.frame)))
					
					#if len(self.frame) == self.length: raise Exception("Frame complete 1")	# TEST
					
					if accept_fn:
						accept_fn(self.byte, self.frame, self.newly_synced)
					
					if len(self.frame) == self.length:
						#raise Exception("Frame complete 2")	# TEST
						self.complete_frame_cnt += 1
						self.frame = []
					
					self.bit_idx = 0
					self.byte = 0
					self.newly_synced = False

class ElementManager():
	def __init__(self):
		self.elements_by_module = {}
		self.elements_map = {}
	def get_element(self, name, safe=True):
		if name not in self.elements_map.keys():
			if not safe:
				return None
			#print "The element '%s' was not found" % (element_name)
			not_found_str = "<element '%s' not found>" % (name)
			self.elements_map[name] = Element(name, name=not_found_str, desc=not_found_str)
		return self.elements_map[name]
	def get_element_ids(self):
		return self.elements_map.keys()
	def get_element_module_ids(self):
		return self.elements_by_module.keys()
	def get_elements_by_module(self, module):
		if module not in self.elements_by_module.keys():
			return None
		return self.elements_by_module[module]
	def load_elements(self, load_path=".", verbose=False):
		abs_load_path = os.path.abspath(load_path)
		if verbose: print "Loading elements from:", abs_load_path
		
		if abs_load_path not in sys.path:
			if verbose: print "Adding '%s' to search path" % (abs_load_path)
			sys.path.append(abs_load_path)
		
		for f in os.listdir(abs_load_path):
			prefix = 'elems_'
			extension = '.py'
			if f.startswith(prefix) and f.endswith(extension):
				module_name = f[:-len(extension)]
				#print module_name
				exec("import " + module_name)
				if verbose: print "Loaded:", f
				module = sys.modules[module_name]
				if not hasattr(module, 'get_elements'):
					if verbose: print "'%s' is not an element definition file" % (module_name)
					continue
				elements = module.get_elements()
				if verbose: print "Found %d elements" % (len(elements))
				if len(elements) == 0:
					continue
				short_module_name = module_name[len(prefix):]
				if short_module_name in self.elements_by_module.keys():
					print "'%s' already in module map (ignoring)" % (short_module_name)
					continue
				self.elements_by_module[short_module_name] = module_element_list = []
				for e in elements:
					if verbose: print str(e)
					if e.id() in self.elements_map.keys():
						print "'%s' already in element map (ignoring)" % (e.id())
						continue
					self.elements_map[e.id()] = e
					module_element_list += [e.id()]
		
		if verbose: print "Loaded %d elements" % (len(self.elements_map.keys()))

class ElementStateManager():
	def __init__(self, element_manager, engine):
		self.element_manager = element_manager
		self.engine = engine
		self.element_state_map = {}
	def get_element_state(self, element, safe=True):
		if not isinstance(element, str):
			element = str(element)
		if element not in self.element_state_map:
			element_instance = self.element_manager.get_element(element, safe)
			if element_instance is None:
				return None
			element_state = state.ElementState(element_instance, self, self.engine)
			self.element_state_map[element] = element_state
		return self.element_state_map[element]

class Engine(state.EventDispatcher, state.Tracker):
	def __init__(self, options):
		state.EventDispatcher.__init__(self, [EVENT_NEW_BYTE])
		self.options = options
		
		self.local_time_now = None
		
		self.element_manager = ElementManager()
		self.element_state_manager = ElementStateManager(self.element_manager, self)
		self.frame_tracker = state.FrameTracker(NUM_MINOR_FRAMES)
		self.subcom_trackers = {}
		self.trackers = {MINOR_FRAME_KEY: self.frame_tracker}
		
		if options.network_address:
			self.deframer = ByteDeframer(MINOR_FRAME_LEN)
			self.net = net.TCPNetwork()
		else:
			self.deframer = SymbolDeframer(MINOR_FRAME_LEN)
			self.net = net.UDPNetwork()
		
		self.server = server.Server(self, self.element_manager, self.element_state_manager, global_log)
		self.ui = ui.UserInterface(self)
	def get_element(self, name, safe=True):
		return self.element_manager.get_element(name, safe)
	def get_element_state(self, element):
		return self.element_state_manager.get_element_state(element)
	def track(self, indices, target, same_tracker=True):	# Currently indices will always be for same tracker in one call
		if same_tracker:
			if indices[0].name not in self.trackers.keys():
				return []
			return self.trackers[indices[0].name].track(indices, target)
		
		#l = []
		for trigger in indices:
			if trigger.name not in self.trackers.keys():
				continue
			#l += 
			self.trackers[trigger.name].track([trigger], target)
		#return l
	def untrack(self, indices, target, same_tracker=True):	# Currently indices will always be for same tracker in one call
		if same_tracker:
			if indices[0].name not in self.trackers.keys():
				return []
			return self.trackers[indices[0].name].untrack(indices, target)
		
		#l = []
		for trigger in indices:
			if trigger.name not in self.trackers.keys():
				continue
			#l += 
			self.trackers[trigger.name].untrack([trigger], target)
		#return l
	def start(self, verbose=False):
		res.load_curves(self.options.load_path, verbose)
		self.element_manager.load_elements(self.options.load_path, verbose)
		
		for k in self.element_manager.get_element_ids():
			element_state = self.get_element_state(k)	# Create element state
			
			#self.frame_tracker.track(element_state.get_trigger_indices(), element_state)	# Force registration with tracker: this needs to be the first handler
			#if self.frame_tracker.is_compatible_target(element_state.get_element().positions()):
			#	self.frame_tracker.track(element_state.get_element().positions().get_trigger_indices(), element_state)
			
			positions = element_state.get_element().positions()
			if positions.is_compatible_tracker(self.frame_tracker):
				self.frame_tracker.track(positions.get_trigger_indices(), element_state)
		
		for subcom_key in EMF_SUBCOM_LIST:
			subcom_tracker = state.SubcomTracker(subcom_key, EMF_SUBCOM_LEN, EMF_COLS[subcom_key], NUM_MINOR_FRAMES)
			self.frame_tracker.track(subcom_tracker.get_trigger_indices(), subcom_tracker.update)
			self.subcom_trackers[subcom_key] = subcom_tracker
			self.trackers[subcom_key] = subcom_tracker
			
			for k in self.element_manager.get_element_ids():
				element_state = self.get_element_state(k)
				positions = element_state.get_element().positions()
				if positions.is_compatible_tracker(subcom_tracker):
					subcom_tracker.track(positions.get_trigger_indices(), element_state)
		
		global _layouts
		if _layouts is None:
			_layouts = []
			for module in self.element_manager.get_element_module_ids():
				element_names = self.element_manager.get_elements_by_module(module)
				module_shortcut = module[0]#.lower()
				_layouts += [(module, element_names, module_shortcut)]
		
		self.net.start(address=self.options.network_address, port=self.options.port)
		
		self.server.start(port=self.options.server_port)
		
		print "Starting UI..."
		self.ui.start(_layouts)
		
		global global_log_fn
		global_log_fn = self.ui.log
		global_log("Running")
	def run(self):
		while True:
			self.local_time_now = datetime.datetime.now()
			
			self.net.run()	# Currently doesn't actually do anything (background thread does)
			
			data = self.net.get_data()
			
			# This try/except block can be disabled for proper debugging
			# It's mainly here as a workaround for windows that are too small and causes curses to throw an exception as the UI assumes the window is larger enough
			#try:
			if True:
				self.deframer.process(data, self.accept_byte)
			
				if not self.ui.run():
					break
			#except Exception, e:
			#	global_log(str(e))
			
			self.server.run()
			
			if ((len(data) == 0) or (self.options.always_sleep)) and (self.options.sleep > 0):
				time.sleep(self.options.sleep)
	def accept_byte(self, byte, frame, sync=False, idx=None):	# Called by Deframer
		self.frame_tracker.update(byte, frame, sync, idx)	# Will update Subcoms
		
		self.dispatch(EVENT_NEW_BYTE, byte=byte, frame=frame, sync=sync, idx=idx)
	def get_local_time_now(self): return self.local_time_now
	def get_state(self):
		return self.deframer.get_state()
	def stop(self):
		self.ui.stop()
		#print "UI shutdown"
		
		if self.server.exception:
			print "An exception occurred in the Server:", self.server.exception
		
		self.server.stop()
		
		if self.net.exception:
			print "An exception occurred in the NetworkThread:", self.net.exception
		
		self.net.stop()
		#print "Net stop"

def main():
	ex = None
	ex_str = None
	
	parser = OptionParser(usage="%prog: [options] [TCP server[:port]]")
	
	parser.add_option("-L", "--load-path", type="string", default='.', help="path to load elements from [default=%default]")
	parser.add_option("-s", "--sleep", type="float", default='0.01', help="loop sleep time (s) [default=%default]")
	parser.add_option("-p", "--port", type="int", default='22222', help="port (UDP server or TCP client) [default=%default]")
	parser.add_option("-P", "--server-port", type="int", default='21012', help="server port [default=%default]")
	parser.add_option("-S", "--always-sleep", action="store_true", default=False, help="always sleep in inner loop [default=%default]")
	parser.add_option("-v", "--verbose", action="store_true", default=False, help="verbose logging outside of UI [default=%default]")
	
	(options, args) = parser.parse_args()
	
	options.network_address = None
	
	if len(args) > 0:
		options.network_address = args[0]
		idx = options.network_address.find(':')
		if idx > -1:
			try:
				options.port = int(options.network_address[idx+1:])
			except Exception, e:
				print "Failed to parse network address port:", e
				return
			options.network_address = options.network_address[:idx]
	
	engine = None
	
	try:
		engine = Engine(options=options)
		
		engine.start(verbose=options.verbose)
		
		engine.run()
	except KeyboardInterrupt:
		#print "Caught CTRL+C"
		pass
	except Exception, e:
		ex = e
		ex_str = traceback.format_exc()
	
	if engine:
		try:
			engine.stop()
			
			print "Engine stopped"
		except Exception, e:
			print "Exception during shutdown:", e
	
	if ex:
		print
		print "Unhandled exception during runtime:", ex
		print ex_str

if __name__ == '__main__':
	main()
