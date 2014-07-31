#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  tlm_graph.py
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
# * allow more than one of the same element
# * automatic re-registration on re-connect

from __future__ import with_statement

import sys, socket, traceback, os, sys, datetime, time, jsonpickle, select, threading

from collections import OrderedDict
from optparse import OptionParser

import numpy
import matplotlib
import matplotlib.pyplot as pyplot
import wx	# For catching when GUI is closed (when using WX MPL backend)

import realtime_graph

""" From server.py:
state['id'] = element_state.get_element().id()
state['time'] = self.engine.get_local_time_now()
state['update_count'] = element_state.update_count
state['value'] = element_state.last_value
state['value_formatted'] = element.formatter().format(element_state.last_value)
state['unit'] = element.unit()
state['valid'] = element_state.last_valid
state['update_time'] = element_state.last_update_time
state['trigger'] = element_state.last_trigger
if element_state.previous_value is not None:
	state['previous_value'] = element_state.previous_value
	state['previous_value_formatted'] = element.formatter().format(element_state.previous_value)
	state['previous_value_time']
"""

class ElementState():
	def __init__(self, element_id, duration=60, x_type='', value_type='out', range_raw=None, range_out=None, *args, **kwds):
		self.element_id = element_id
		#if range_raw is not None and isinstance(range_raw, str): range_raw = parse_me(range_raw)	# FIXME
		#if range_out is not None and isinstance(range_out, str): range_out = parse_me(range_out)	# FIXME
		if isinstance(duration, str): duration = float(duration)
		self.duration = duration
		self.x_type = x_type
		self.range_raw = range_raw
		self.range_out = range_out
		self.value_type = value_type
		self.data = None
		#self.y = []
		self.y = numpy.array([])
		self.unit = ""
		self.plot = None
	def init(self, res):
		if res.has_key('range_raw') and self.range_raw is None:
			self.range_raw = res['range_raw']
			#print "%s: range (raw): %s" % (self.element_id, self.range_raw)
		if res.has_key('range_out') and self.range_out is None:
			self.range_out = res['range_out']
			#print "%s: range (out): %s" % (self.element_id, self.range_out)
		if res.has_key('unit'):
			self.unit = res['unit']
	def get_value_type(self):
		if not isinstance(self.value_type, str) or len(self.value_type) == 0: return 'raw'
		return self.value_type
	def get_range(self, value_type=None):
		if value_type is None:
			value_type = self.get_value_type()
		if value_type.lower() == 'out':
			rng = self.range_out
		elif value_type.lower() == 'raw':
			rng = self.range_raw
		if not rng: rng = [0,255]
		return rng
	def get_value_str(self, unit=True):
		if self.data is None: return ""
		if self.get_value_type() == 'raw':
			s = str(self.data['value'])
		else:
			s = str(self.data['value_formatted'])
		if unit and self.unit is not None and len(self.unit) > 0:
			s += " " + self.unit
		return s
	def get_graph_data(self):
		#return numpy.array(self.y)
		return self.y
	def get_graph_x(self):
		if self.x_type != '':
			raise Exception("X-axis types not implemented")
		return numpy.linspace(0, len(self.y), len(self.y), False)
	def get_graph_x_range(self):
		return (max(0, len(self.y) - self.duration), max(self.duration, len(self.y)))
	def add_data(self, res):
		self.data = res
		try:
			v_str = self.get_value_str(unit=False)
			v = float(v_str)
		except Exception, e:
			print "Cannot convert value to float:", v_str
			return
		#self.y += [v]
		self.y = numpy.append(self.y, [v])

class Network(threading.Thread):
	def __init__(self, destination, buffer_size=1024, sleep=1, auto_reconnect=True, *args, **kwds):
		threading.Thread.__init__(self, name="Network", *args, **kwds)
		self.setDaemon(True)
		self.destination = destination
		self.sock = None
		self.buffer_size = buffer_size
		self.sleep = sleep
		self.auto_reconnect = auto_reconnect
		self.update_event = threading.Event()
		self.lock = threading.Lock()
		self.keep_running = True
		self.reset()
	def reset(self):
		self.buffer = ""
		self.seq = 0
		self.msgs = []
	def set_auto_reconnect(self, auto_reconnect):
		self.auto_reconnect = auto_reconnect
	def get_msgs(self):
		with self.lock:
			msgs = self.msgs
			self.msgs = []
			self.update_event.clear()
			return msgs
	def connect(self, dest=None):
		if dest is None:
			dest = self.destination
		self.disconnect()
		
		with self.lock:
			while self.keep_running:
				try:
					print "Connecting to:", self.destination
					
					self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					self.sock.connect(self.destination)
					
					print "Connected"
				except socket.error, (e, msg):
					if e == 111 or e == 113: # Connection refused, No route to host
						print "Connection refused. Re-trying..."
						time.sleep(self.sleep)
						continue
					
					print "Exception while connecting:", (e, msg)
					return False
				break
		
		return True
	def run(self):
		while self.keep_running:
			try:
				msgs = self._receive()
				if len(msgs) > 0:
					with self.lock:
						self.msgs += msgs
						self.update_event.set()
			except socket.error, (e, msg):
				if e == 104:	# Connection reset by peer
					print "Connection reset"
					self.disconnect()
					if self.auto_reconnect:
						if self.sleep > 0:
							time.sleep(self.sleep)
						self.connect()
						continue
					else:
						self.update_event.set()
						break
				print "Unexpected socket error:", (e, msg)
				break
			except Exception, e:
				print "Unhandled Network exception:", e
				break
	def disconnect(self):
		with self.lock:
			if self.sock is None:
				return
			
			try:
				self.sock.shutdown(socket.SHUT_RDWR)
				self.sock.close()
				self.sock = None
			except Exception, e:
				pass
			
			self.reset()
	def shutdown(self):
		self.keep_running = False
		if disconnect:
			self.disconnect()
		self.stop()
	def stop(self):
		if not self.isAlive():
			return False
		keep_running = self.keep_running
		self.keep_running = False
		print "Waiting for thread to finish..."
		self.join()
		self.keep_running = keep_running
		return True
	def _post(self, msg, new_line=True):
		if not isinstance(msg, str):
			msg = jsonpickle.encode(msg)
		if new_line:
			msg += '\n'
		self.sock.send(msg)
	def transact(self, msg):
		if not self.keep_running:
			print "Cannot start transaction when not running"
			return None
		while self.keep_running:
			try:
				return self._transact(msg)
			except socket.error, (e, msg):
				#if e == 32:	# Broken pipe
				#	print "Disconnected"
				print "Socket error:", (e, msg)
				
				if self.auto_reconnect:
					if not self.keep_running:
						return None
					self.connect()
					continue
				else:
					return None
			#except Exception, e:
			#	print "Exception during transaction:", e
			#	raise
			#return None
	def _transact(self, msg):
		msg['seq'] = self.seq
		self.seq += 1
		self._post(msg)
		msgs = self._receive(msg['seq'])
		if len(msgs) == 0:
			return None
		return msgs[0]
	def _receive(self, seq=None):
		msgs = []
		
		cnt = 0
		while self.keep_running:
			if cnt > 0:
				ready_to_read, ready_to_write, in_error = select.select([self.sock],[],[],0)
				if len(ready_to_read) == 0:
					break
			
			data = self.sock.recv(self.buffer_size)
			if len(data) == 0:
				#print "Connection closed"
				raise socket.error(104, "Connection reset")
				break
			
			cnt += 1
			self.buffer += data
			lines = self.buffer.splitlines(True)
			
			for line in lines:
				if line[-1] != '\n':
					self.buffer = line
					break
				line = line.strip()
				
				try:
					try:
						msg = jsonpickle.decode(line)
					except Exception, e:
						raise Exception("Could not decode JSON:\n%s" % (line))
					
					if msg.has_key('error') and msg['error'] is not None:
						print "Error at server: %s\n%s" % (msg['error'], msg)
					
					# With 'seq' this ignores previous messages AND future decoded lines
					if seq:
						if msg.has_key('seq'):
							if seq == msg['seq']:
								return [msg]
						cnt = 0	# Don't abort the loop if there's no more to read
					else:
						msgs += [msg]
				except Exception, e:
					print "Exception in message decode: %s" % (e)
			else:
				self.buffer = ""
		
		return msgs

def main():
	parser = OptionParser(usage="%prog: [options] <destination>[:port] <element>[,<length>] ...")
	
	parser.add_option("-p", "--port", type="int", default=21012, help="TCP port [default=%default]")
	parser.add_option("-s", "--sleep", type="float", default=1.0, help="reconnect sleep time (s) [default=%default]")
	parser.add_option("-T", "--timeout", type="float", default=0.01, help="GUI event handler timeout (s) [default=%default]")
	parser.add_option("-d", "--duration", type="float", default=60.0, help="default duration (s) [default=%default]")
	parser.add_option("-t", "--type", type="string", default="out", help="default value type (raw, out) [default=%default]")
	parser.add_option("-x", "--x-type", type="string", default="", help="default X-axis type (blank: consecutive samples, time) [default=%default]")
	#parser.add_option("-v", "--verbose", action="store_true", default=False, help="verbose logging [default=%default]")
	parser.add_option("-n", "--no-reconnect", action="store_true", default=False, help="do not automatically reconnect [default=%default]")
	
	(options, args) = parser.parse_args()
	
	if len(args) < 1:
		print "Supply destination address"
		return
	
	network_address = args[0]
	idx = network_address.find(':')
	if idx > -1:
		try:
			options.port = int(network_address[idx+1:])
		except Exception, e:
			print "Failed to parse network address port:", e
			return
		network_address = network_address[:idx]
	
	destination = (network_address, options.port)
	
	##################################################################
	
	element_states = {}
	elements_ordered = []
	
	for element_spec in args[1:]:
		parts = element_spec.split(',')
		element_id = parts[0]
		kwdargs = {}
		for part in parts:
			subparts = part.split('=')
			if len(subparts) != 2:
				continue
			kwdargs[subparts[0].lower()] = subparts[1]
		if 'duration' not in kwdargs.keys(): kwdargs['duration'] = options.duration
		if 'value_type' not in kwdargs.keys(): kwdargs['value_type'] = options.type
		if 'x_type' not in kwdargs.keys(): kwdargs['x_type'] = options.x_type
		state = ElementState(element_id, **kwdargs)
		if element_id in element_states.keys():
			print "Element \'%s\' already supplied" % (element_id)
			continue
		element_states[element_id] = state
		elements_ordered += [(element_id, state)]
	
	if len(element_states.keys()) == 0:
		print "Supply at least one element ID"
		return
	
	element_states = OrderedDict(elements_ordered)
	
	##################################################################
	
	try:
		net = Network(destination, sleep=options.sleep, auto_reconnect=not options.no_reconnect)
		if not net.connect():
			return
		
		registration = {'action':'register', 'data':element_states.keys()}
		
		response = net.transact(registration)
		if response is None:
			print "Invalid response"
			net.disconnect()
			return
		
		successful_elements, failed_elements = response['result']
		
		for failed_element in failed_elements:
			print "Failed to register:", failed_element
			del element_states[failed_element]
		
		successful_elements_ids = []
		for successful_element in successful_elements:
			successful_element_id = successful_element['id']
			element_states[successful_element_id].init(successful_element)
			if successful_element_id not in element_states.keys():
				print "Element not found in supplied list:", successful_element_id
			successful_elements_ids += [successful_element_id]
		
		for element in element_states.keys():
			if element not in successful_elements_ids:
				print "Element supplied but not successful:", element
				del element_states[failed_element]
		
		if len(element_states.keys()) == 0:
			print "No elements remained to be monitored"
			net.disconnect()
			return
		
		print "Monitoring:"
		print "\n".join(element_states.keys())
		
		##############################################################
		
		font = {
			#'family' : 'normal',
			#'weight' : 'bold',
			'size'   : 10
		}
		
		matplotlib.rc('font', **font)
		
		padding = 0.05
		spacing = 0.2
		figure_width = 8
		figure_height = 10-4	# MAGIC
		
		graph_count = len(element_states.keys())
		
		# FIXME
		if graph_count > 6:
			graph_pos = 330
		elif graph_count > 4:
			graph_pos = 230
		elif graph_count > 2:
			graph_pos = 220
			figure_height *= 2
			figure_width *= 2
		elif graph_count == 2:
			graph_pos = 120
			figure_width *= 2
		else:
			graph_pos = 110
		
		figsize = (figure_width, figure_height)
		padding = {'wspace':spacing,'hspace':spacing,'top':1.-padding,'left':padding,'bottom':padding,'right':1.-padding}
		graph_window = realtime_graph.realtime_graph(title="", show=True, manual=True, redraw=False, figsize=figsize, padding=padding)
		
		pos_count = 0
		#for graph_idx in range(graph_count):
		for element_id in element_states.keys():
			element_state = element_states[element_id]
			
			#if graph_count > 2:
			#    pos_offset = ((pos_count % 2) * 2) + (pos_count / 2) + 1   # Re-order column-major
			#else:
			pos_offset = pos_count + 1
			subplot_pos = (graph_pos + pos_offset)
			
			y_limits = tuple(element_state.get_range())
			
			#print pos_count, element_id, y_limits, element_state.duration
			
			element_state.plot = sub_graph = realtime_graph.realtime_graph(
				parent=graph_window,
				show=True,	# True to add plot
				redraw=False,
				sub_title=element_state.element_id,
				pos=subplot_pos,
				y_limits=y_limits,
				x_range=element_state.duration,
			)
			
			sub_graph.set_y_limits(None)
			
			pos_count += 1
		
		graph_window.redraw()
		
		##############################################################
		
		print "Starting Network thread..."
		
		net.start()	# Thread will automatically reconnect to server is connection fails
		# FIXME: Need to automatically re-register elements as well
		
		while True:
			graph_window.run_event_loop(options.timeout)
			
			if not net.update_event.isSet():
				continue
			
			msgs = net.get_msgs()
			if len(msgs) == 0:
				print "Disconnected (not reconnecting)"
				graph_window.go_modal()
				break
			
			update_cnt = 0
			
			for msg in msgs:
				if not msg.has_key('result'):
					continue
				state = msg['result']
				if state is None:
					continue
				element_id = state['id']
				if element_id not in element_states.keys():
					print "Bad element ID:", element_id
					continue
				
				element_state = element_states[element_id]
				element_state.add_data(state)
				
				update_cnt += 1
				
				value_str = element_state.get_value_str()
				graph_data = element_state.get_graph_data()
				graph_x = element_state.get_graph_x()
				graph_x_range = element_state.get_graph_x_range()
				
				sub_title = "%s: %s" % (element_id, value_str)
				
				element_state.plot.update(data=graph_data, x=graph_x, x_range=graph_x_range, sub_title=sub_title, autoscale=False, redraw=False)
			
			if update_cnt > 0:
				graph_window.redraw()
	except KeyboardInterrupt:
		pass
	except wx._core.PyDeadObjectError:
		pass
	except Exception, e:
		print "Unhandled exception:", e
		print traceback.format_exc()
	
	print "Shutting down..."
	
	try:
		net.set_auto_reconnect(False)
		
		#net.shutdown()	# 'stop' and 'disconnect' but this prevents future 'transact'
		
		net.stop()
		
		if True:	# This is just to test (optional since disconnection at the server will automatically unregister all elements)
			unregistration = {'action':'unregister', 'data':element_states.keys()}
			
			response = net.transact(unregistration)
			if response is not None:
				successful_elements, failed_elements = response['result']
			
				for failed_element in failed_elements:
					print "Failed to unregister:", failed_element
				
				print "Unregistered:"
				print "\n".join(successful_elements)
			else:
				print "Invalid response"
		
		net.disconnect()
	except KeyboardInterrupt:
		pass
	except Exception, e:
		print "Unhandled exception during shutdown:", e
	
	return 0

if __name__ == '__main__':
	main()
