#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  server.py
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

from __future__ import with_statement

import sys, threading, traceback, socket, SocketServer, time, traceback, jsonpickle, datetime

import utils, primitives

_LISTEN_ADDR = "0.0.0.0"
_LISTEN_PORT = 21012

class DatetimeHandler(jsonpickle.handlers.BaseHandler):
	def flatten(self, obj, data):
		return obj.isoformat()
jsonpickle.handlers.registry.register(datetime.datetime, DatetimeHandler)

class ThreadedTCPRequestHandler(SocketServer.StreamRequestHandler): # BaseRequestHandler
	# No __init__
	def setup(self):
		SocketServer.StreamRequestHandler.setup(self)
		#print "==> Connection from:", self.client_address#, "in thread", threading.currentThread().getName()
		self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
		with self.server.client_lock:
			self.server.clients.append(self)
		self.registration_map = {}
	def handle(self):
		buffer = ""
		while True:
			data = ""   # Initialise to nothing so if there's an exception it'll disconnect
			try:
				data = self.request.recv(self.server.buffer_size)
			except socket.error, (e, msg):
				#if e != 104:    # Connection reset by peer
				#	print "==>", self.client_address, "-", msg
				pass
			if len(data) == 0:
				break
			
			buffer += data
			lines = buffer.splitlines(True)
			for line in lines:
				if line[-1] != '\n':
					buffer = line
					break
				line = line.strip()
				
				try:
					msg = jsonpickle.decode(line)
					
					self.server.server.update((self.client_address, msg))
				except Exception, e:
					pass
			else:
			    buffer = ""
	def finish(self):
		#print "==> Disconnection from:", self.client_address
		self.server.server.untrack(self)
		
		with self.server.client_lock:
			self.server.clients.remove(self)
		try:
			SocketServer.StreamRequestHandler.finish(self)
		except socket.error, (e, msg):
			#if (e != 32): # Broken pipe
			#	print "==>", self.client_address, "-", msg
			pass
	def post(self, msg, new_line=True):
		try:
			if not isinstance(msg, str):
				msg = jsonpickle.encode(msg, unpicklable=False)
			if new_line:
				msg += '\n'
			self.wfile.write(msg)
		except Exception, e:
			#print "Could not post to %s: %s\n%s" % (str(self.client_address), e, str(msg))
			pass

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
	pass

class Server():
	def __init__(self, engine, element_manager, element_state_manager, log):
		self.engine = engine
		self.element_manager = element_manager
		self.element_state_manager = element_state_manager
		self.log = log
		self.exception = None
		self.server = None
		self.server_thread = None
		self.update_lock = threading.Lock()
		self.pending_updates = []
		self.registration_map = {}
	def start(self, address=_LISTEN_ADDR, port=_LISTEN_PORT, buffer_size=1024, sleep=1.0):
		if self.server:
			raise Exception("Server already started")
		if self.server_thread:
			raise Exception("Server thread already exists")
		
		listen_address = (address, port)
		
		print "Starting server on:", listen_address
		
		while True:
			try:
				self.server = ThreadedTCPServer(listen_address, ThreadedTCPRequestHandler)
				
				self.server.server = self
				self.server.client_lock = threading.Lock()
				self.server.clients = []
				self.server.update_event = threading.Event()
				self.server.buffer_size = buffer_size
				self.server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				
				self.server_thread = threading.Thread(target=self.server.serve_forever)
				self.server_thread.setDaemon(True)
				self.server_thread.start()
			except socket.error, (e, msg):
				print "    Socket error:", msg
				if (e == 98):
					print "    Waiting, then trying again..."
					time.sleep(sleep)
					continue
				raise
			#except Exception, e:
			#	print "Unhandled exception while starting Server:", e
			break
		
		print "Server listening on:",  self.server.server_address
	def untrack(self, client_connection):
		if self.server is None:
			return
		with self.update_lock:
			with self.server.client_lock:
				# Remove all pending updates for this client
				self.pending_updates = filter(lambda x: x[0] != client_connection.client_address, self.pending_updates)
				
				# Remove this client for the server's trigger registration map
				triggers_to_remove = []
				triggers_removed = []
				for trigger_index in self.registration_map.keys():
					if client_connection.client_address in self.registration_map[trigger_index]:
						self.registration_map[trigger_index].remove(client_connection.client_address)
						triggers_removed += [trigger_index]
						if len(self.registration_map[trigger_index]) == 0:
							triggers_to_remove += [trigger_index]
				
				for trigger_index in triggers_to_remove:
					del self.registration_map[trigger_index]
				
				element_states = self._get_client_element_states(client_connection)
				
				#self.log("%s: Untrack: %s" % (client_connection.client_address, ", ".join([x.get_element().id() for x in element_states])))
				#self.log("%s: Empty server trigger indices: %s (total: %s)" % (client_connection.client_address, len(triggers_to_remove), len(self.registration_map.keys())))
				
				untracked_elements = self._untrack(element_states, client_connection)
				
				if len(triggers_removed) > 0:
					self.log("%s: Untracked: %s" % (client_connection.client_address, ", ".join([x.get_element().id() for x in untracked_elements])))
	def _get_client_element_states(self, client_connection):	# Assumes locks are taken
		element_states = []
		
		# Compile a unique list of all the elements that this connection had registered
		for trigger_index in client_connection.registration_map.keys():
			_element_states = client_connection.registration_map[trigger_index]
			for element_state in _element_states:
				if element_state not in element_states:
					element_states += [element_state]
		
		return element_states
	def _untrack(self, element_states, client_connection):	# Assumes locks are taken
		# Remove from that list those elements that are still registered by other clients
		if self.server is not None:	# If server is shutdown while clients are still connected
			for client in self.server.clients:
				if client == client_connection:
					continue
				
				other_element_states = self._get_client_element_states(client)
				for element_state in other_element_states:
					if element_state in element_states:
						element_states.remove(element_state)
		
		#self.log("%s: Untrack: %s" % (client_connection.client_address, ", ".join([x.get_element().id() for x in element_states])))
		
		# Untrack the remaining elements (that were only registered by this client)
		for element_state in element_states:
			self.engine.untrack(element_state.get_element().positions().get_trigger_indices(mode=self.engine.options.mode), self)
		
		return element_states
	def run(self):
		with self.update_lock:
			for update in self.pending_updates:
				client_address, msg = update
				
				client = self.get_client(client_address)	 # Lock released below
				if not client:
					raise Exception("Client went missing: %s" % (str(client_address)))
				
				successful_elements, failed_elements = [], []
				
				response = {'action':None, 'result':(successful_elements,failed_elements), 'error':None, 'seq':None}
				
				try:
					action				= msg['action'].lower()
					data				= msg['data']
					
					response['action']	= action
					response['seq']		= msg['seq']
					
					if action == "register":
						for element_id in data:
							element_state = self.element_state_manager.get_element_state(element_id, safe=False)
							if element_state is None:
								failed_elements += [element_id]
								continue
							
							trigger_indices = element_state.get_element().positions().get_trigger_indices(mode=self.engine.options.mode)
							self.engine.track(trigger_indices, self)
							
							for trigger_index in trigger_indices:
								if trigger_index not in self.registration_map.keys():
									self.registration_map[trigger_index] = []
								self.registration_map[trigger_index] += [client_address]
								
								if trigger_index not in client.registration_map.keys():
									client.registration_map[trigger_index] = []
								client.registration_map[trigger_index] += [element_state]
							
							element_info = {'id':element_id}
							
							element_info['unit'] = element_state.get_element().unit()
							
							range_info = utils.find_subclass(primitives.RangeInfo, [element_state.get_element().validator(), element_state.get_element().formatter()])
							if range_info:
								element_info['range_raw'] = (min(range_info.rng), max(range_info.rng))
								element_info['range_out'] = (min(range_info.points), max(range_info.points))
							
							successful_elements += [element_info]
							
							self.log("%s: Registered: %s" % (client_address, ", ".join([x['id'] for x in successful_elements])))
					elif action == "unregister":
						self.log("%s: Unregistering: %s" % (client_address, ", ".join(map(str, data))))
						
						registered_element_states = self._get_client_element_states(client)
						element_states = []
						
						# Filter out bad elements, or those that aren't registered for this client
						for element_id in data:
							element_state = self.element_state_manager.get_element_state(element_id, safe=False)
							if element_state is None or element_state not in registered_element_states:
								failed_elements += [element_id]
								continue
							
							if element_id in successful_elements:
								continue
							
							successful_elements += [element_id]
							element_states += [element_state]
						
						# Remove the elements from the client's map. If the trigger's list is then empty, remove it too, and then remove the client from the server's map.
						triggers_to_remove = []
						for element_state in element_states:
							for trigger_index in client.registration_map.keys():
								client_registration_list = client.registration_map[trigger_index]
								if element_state in client_registration_list:
									client_registration_list.remove(element_state)
								if len(client_registration_list) == 0:
									del client.registration_map[trigger_index]
									triggers_to_remove += [trigger_index]
						
						# If the client no longer tracks a trigger index, remove the client from the server's map. If the server's list for that trigger index is empty, remove it too.
						for trigger_index in triggers_to_remove:
							if trigger_index not in self.registration_map.keys():
								raise Exception("Client %s trigger index %s not in server map %s" % (client_address, trigger_index, self.registration_map.keys()))
							
							client_address_list = self.registration_map[trigger_index]
							if client_address not in client_address_list:
								raise Exception("Client %s not in server's trigger index %s list %s" % (client_address, trigger_index, client_address_list))
							
							client_address_list.remove(client_address)
							
							if len(client_address_list) == 0:
								del self.registration_map[trigger_index]
						
						untracked_elements = self._untrack(element_states, client)
						
						self.log("%s: Unregistered: %s" % (client_address, ", ".join([x.get_element().id() for x in untracked_elements])))
					else:
						res['error'] = "Action unrecognised: '%s'" % (msg['action'])
				except Exception, e:
					print "While Server was handling message:", e
					res['error'] = str(e)
					raise
				
				client.post(response)
				
				self.server.client_lock.release()
			
			self.pending_updates = []
	def __call__(self, *args, **kwds):
		with self.update_lock:
			trigger = kwds['trigger']
			
			res, map_res = trigger.check_map(self.registration_map)
			
			if not res:
			# Callback might be waiting for lock above while a client is unregistering/disconnect, which means that update will be stale if the trigger has since been unregistered.
			# Assuming that is always the case when the trigger is not found, ignore this silently.
				return
			#	self.log("%s not in server registration map" % (str(trigger)))
			#	raise Exception("%s not in %s" % (trigger, self.registration_map.keys()))
			
			triggered_client_addresses = map_res
			
			for client_address in triggered_client_addresses:
				client = self.get_client(client_address)
				if not client:
					raise Exception("Client went missing: %s" % (str(client_address)))
				
				res, map_res = trigger.check_map(client.registration_map)
				if not res:
					raise Exception("Trigger %s not found in client registration map for %s" % (str(trigger), client_address))
				element_states = map_res
				
				for element_state in element_states:
					if element_state.last_value is None:
						continue
					
					element = element_state.get_element()
					
					state = {}
					response = {'result':state, 'error':None}
					
					try:
						state['id']				= element_state.get_element().id()
						state['time']			= self.engine.get_local_time_now()
						state['update_count']	= element_state.update_count
						state['value']			= element_state.last_value
						state['value_formatted']= element.formatter().format(element_state.last_value)
						state['valid']			= element_state.last_valid
						state['update_time']	= element_state.last_update_time
						state['trigger']		= element_state.last_trigger
						if element_state.previous_value is not None:
							state['previous_value']				= element_state.previous_value
							state['previous_value_formatted']	= element.formatter().format(element_state.previous_value)
							state['previous_value_time']		= element_state.previous_value_time
					except Exception, e:
						response['error'] = str(e)
					
					client.post(response)
				
				self.server.client_lock.release()
	def get_client(self, address, keep_lock=True):
		self.server.client_lock.acquire()
		client = None
		for c in self.server.clients:
			if c.client_address == address:
				client = c
				break
		if client is None or not keep_lock:
			self.server.client_lock.release()
		return client
	def update(self, update):
		with self.update_lock:
			self.pending_updates += [update]
	def stop(self):
		print "Shutting down server..."
		if self.server:
			self.server.shutdown()
			
			with self.server.client_lock:
				for client in self.server.clients:
					print "Disconnecting client:", client.client_address
					client.request.shutdown(socket.SHUT_RDWR)
					client.request.close()
			
			self.server = None
		print "Waiting for server thread..."
		if self.server_thread:
			self.server_thread.join()
			self.server_thread = None
		print "Server stopped"

def main():
	return 0

if __name__ == '__main__':
	main()
