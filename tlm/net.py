#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  net.py
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

# FIXME: Abstract to data source for file replay

from __future__ import with_statement

import socket, threading, datetime, struct, random, time

from input import *

_UDP_IP = "127.0.0.1"
_PORT = 22222
_BUFFER_SIZE = 1024

# BorIP flags (see http://wiki.spench.net/wiki/BorIP#Streaming_UDP_Protocol)
BF_HARDWARE_OVERRUN	= 0x01
BF_NETWORK_OVERRUN	= 0x02
BF_BUFFER_OVERRUN	= 0x04
BF_EMPTY_PAYLOAD	= 0x08
BF_STREAM_START		= 0x10
BF_STREAM_END		= 0x20
BF_BUFFER_UNDERRUN	= 0x40
BF_HARDWARE_TIMEOUT	= 0x80

class RateCalculator():
	def __init__(self, averaging_period=5.0, minimum_averaging_factor=0.5):
		self.averaging_period = averaging_period
		self.minimum_averaging_factor = minimum_averaging_factor
		RateCalculator.reset(self)
	def reset(self):
		self.stats_history = []
		self.ave_rate = 0.0
	def calculate_statistics(self, time=None):
		if time is None:
			time = datetime.datetime.now()
		time_last = time - datetime.timedelta(seconds=self.averaging_period)
		cnt = 0
		for buf in self.stats_history:
			if buf.get_local_time() > time_last:
				break
			cnt += 1
		self.stats_history = self.stats_history[cnt:]
		
		if len(self.stats_history) <= 1:
			self.ave_rate = 0.0
			return
		
		total_bytes = sum(map(lambda x: len(x.get_buffer()), self.stats_history))
		first = self.stats_history[0]
		last = self.stats_history[-1]
		time_diff = last.get_local_time() - first.get_local_time()
		if time_diff.total_seconds() < (self.averaging_period * self.minimum_averaging_factor):
			return
		self.ave_rate = 1.*total_bytes / time_diff.total_seconds()
	def get_ave_rate(self): return self.ave_rate

class TCPNetworkThread(threading.Thread, RateCalculator):
	def __init__(self, network, address, timeout=0.1, sleep=1.0, *args, **kwargs):
		threading.Thread.__init__(self, name="Network", *args, **kwargs)
		RateCalculator.__init__(self, *args, **kwargs)
		self.network = network
		self.address = address
		self.timeout = timeout
		self.sleep = sleep
		self.sock = None
		self.keep_connecting = True
		self.connected = False
		self.connecting = False
		self.parser = PKParser()
		self.reset()
	def reset(self):
		self.drop_count = 0
		self.parser.reset()
		RateCalculator.reset(self)
	def log(self, msg):
		self.network.log(msg)
	def get_drop_count(self): return self.drop_count
	def disconnect(self, final=False):
		if self.sock:
			try:
				self.sock.shutdown(socket.SHUT_RDWR)
				self.sock.close()
			except:
				pass
			self.sock = None
			self.connected = False
			self.connecting = False
		if final:
			self.keep_connecting = False
	def run(self):
		#print "In NetworkThread"
		while self.keep_connecting:
			self.disconnect()
			
			try:
				self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				self.connecting = True
				self.sock.connect(self.address)
				if self.timeout > 0:
					self.sock.settimeout(self.timeout)
				self.connecting = False
				self.connected = True
			except socket.error, (e, msg):
				if e == 111 or e == 113: # Connection refused, No route to host
					#print "Connection refused. Re-trying..."
					time.sleep(self.sleep)
					continue
				self.network.exception = socket.error(e, msg)	# FIXME: Check this
				break
			except Exception, e:
				self.network.exception = e
				break
			
			self.reset()
			
			while True:
				try:
					data = self.sock.recv(self.network.buffer_size)
					
					if len(data) == 0:
						break
					
					if not self.parser.parse(data):	# FIXME: Whole frames will throw off stats calculation
						continue
					
					frames = self.parser.get_frames()
					
					self.stats_history += frames
					
					self.log(self.parser.last_log)
					
					self.calculate_statistics(frames[-1].get_local_time())	# FIXME: On connection, TCP buffer will be filled, so initial rate will be high
					
					for f in frames:
						self.network.enqueue_data(f)
				except socket.timeout:
					self.calculate_statistics()
				except socket.error, (e, msg):
					if e != 104:    # Connection reset by peer
						#print "==>", self.client_address, "-", msg
						self.network.exception = socket.error(e, msg)
						self.disconnect(final=True)
					break
				except Exception, e:
					#print "Encountered exception in NetworkThread:", e
					self.network.exception = e
					self.disconnect(final=True)
					break
		
		self.disconnect()

class UDPNetworkThread(threading.Thread, RateCalculator):
	def __init__(self, network, borip, *args, **kwargs):
		threading.Thread.__init__(self, name="Network", *args, **kwargs)
		RateCalculator.__init__(self, *args, **kwargs)
		self.network = network
		self.borip = borip
		self.reset()
	def reset(self):
		self.last_seq = None
		self.drop_count = 0
		RateCalculator.reset(self)
	def log(self, msg):
		self.network.log(msg)
	def get_drop_count(self): return self.drop_count
	def run(self):
		#print "In NetworkThread"
		while True:
			try:
				if self.network.sock is None:
					break
				
				data, addr = self.network.sock.recvfrom(self.network.buffer_size)
				
				flags = Buffer.FLAG_NONE
				
				if self.borip:
					borip_header_length = 4
					if len(data) < borip_header_length:
						# FIXME: Raise error
						continue
					flags, notification, seq = struct.unpack("BBH", data[:borip_header_length])
					
					if flags & BF_STREAM_START:
						self.log("Stream start")
						self.reset()
					
					#if random.random() < 0.01: seq = -1	# Simulate packet loss
					
					if self.last_seq is not None:
						if seq != ((self.last_seq + 1) % (1 << 16)):
							flags |= Buffer.FLAG_DROP
							self.drop_count += 1
					self.last_seq = seq
					
					if flags & BF_STREAM_END:
						flags |= Buffer.FLAG_LAST
					
					data = data[borip_header_length:]
				
				net_buffer = Buffer(data, flags)
				
				self.stats_history += [net_buffer]
				
				self.calculate_statistics(net_buffer.get_local_time())
				
				self.network.enqueue_data(net_buffer)
			except socket.timeout:
				self.calculate_statistics()
			except Exception, e:
				#print "Encountered exception in NetworkThread:", e
				self.network.exception = e
				break

class NetworkInput(Input):
	def __init__(self, *args, **kwds):
		Input.__init__(self, *args, **kwds)
		self.thread = None
		self.buffers = []
		self.lock = threading.Lock()
		#self.last_enqueue_time = None
		self.last_get_time = None
		self.exception = None
		self.last_thread_message = ""
	def start(self, *args, **kwds):
		self.exception = None
		if self.thread:
			raise Exception("Thread already created")
		return True
	def run(self):
		pass
	def stop(self):
		if self.thread:
			print "Waiting for NetworkThread..."
			self.thread.join()	# Waits forever
			self.thread = None
	def enqueue_data(self, data):
		with self.lock:
			self.buffers += [data]
			self.last_enqueue_time = datetime.datetime.now()
	def get_data(self):
		with self.lock:
			buffers = self.buffers
			self.buffers = []
			self.last_get_time = datetime.datetime.now()
			return buffers
	def get_time_diff(self):
		with self.lock:
			if self.last_get_time is None or self.last_enqueue_time is None:
				return datetime.timedelta(0)
			return self.last_get_time - self.last_enqueue_time
	#def get_status_string(self):
	#	return ""
	def log(self, msg):
		self.last_thread_message = msg

class TCPNetwork(NetworkInput):
	def __init__(self, buffer_size=_BUFFER_SIZE, timeout=0.1, *args, **kwds):
		NetworkInput.__init__(self, *args, **kwds)
		self.buffer_size = buffer_size
		self.timeout = timeout
	def start(self, address, port=_PORT, *args, **kwds):
		NetworkInput.start(self, *args, **kwds)
		self.thread = TCPNetworkThread(self, (address, port), self.timeout)
		self.thread.setDaemon(True)
		self.thread.start()
	def stop(self):
		if self.thread:
			self.thread.disconnect(final=True)
		NetworkInput.stop(self)
	def get_status_string(self):
		if self.thread is None:
			return ""
		if self.thread.connected:
			status = "Connected to %s" % (str(self.thread.sock.getpeername()))
			status += ", rate: %04d" % (int(self.thread.get_ave_rate() * 8))
		elif self.thread.connecting:
			status = "Connecting to %s" % (str(self.thread.address))
		else:
			status = "Disconnected"
		status += (", bad lines: %d" % (self.thread.parser.bad_line_cnt))
		if len(self.last_thread_message) > 0:
			status += ", " + self.last_thread_message
		return status

class UDPNetwork(NetworkInput):
	def __init__(self, buffer_size=_BUFFER_SIZE, timeout=0.1, *args, **kwds):
		NetworkInput.__init__(self, *args, **kwds)
		self.sock = None
		self.buffer_size = buffer_size
		self.timeout = timeout
	def start(self, address=_UDP_IP, port=_PORT, *args, **kwds):
		NetworkInput.start(self, *args, **kwds)
		if address is None:
			address = _UDP_IP
		if self.sock:
			raise Exception("Socket already exists")
		try:
			self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			self.sock.bind((address, port))
			if self.timeout > 0:
				self.sock.settimeout(self.timeout)
		except Exception, e:
			raise e
		self.thread = UDPNetworkThread(self, borip=True)
		self.thread.setDaemon(True)
		self.thread.start()
	def stop(self):
		if self.sock:
			#print "Closing socket..."
			self.sock.close()	# Should cause thread to exit (doesn't)
			self.sock = None
		NetworkInput.stop(self)
	def get_status_string(self):
		if self.thread is None:
			return ""
		status = "Rate: %04d, drops: %04d" % (int(self.thread.get_ave_rate()), self.thread.get_drop_count())
		if len(self.last_thread_message) > 0:
			status += ", " + self.last_thread_message
		return status

def main():
	return 0

if __name__ == '__main__':
	main()
