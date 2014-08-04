#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  feed.py
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

import sys, threading, socket, SocketServer, time, traceback, datetime, curses

from optparse import OptionParser

import tcp_server

import net, input

LISTEN_RETRY_INTERVAL = 5

class History():	# FIXME: Subclass RateCalculator from this
	def __init__(self, history_length):
		self.length = history_length
		self.history = []
	def get_history(self): return self.history
	def add_to_history(self, frame, time_now=None):
		self.history += [frame]
		
		if time_now is None:
			time_now = datetime.datetime.now()
		
		time_last = time_now - datetime.timedelta(seconds=self.length)
		
		cnt = 0
		for frame in self.history:
			if frame.get_local_time() > time_last:
				break
			cnt += 1
		
		self.history = self.history[cnt:]
	def in_history(self, frame):
		idx = 0
		for f in self.get_history():
			if frame.get_buffer() == f.get_buffer():
				return idx
			idx += 1
		return -1

class FeedSource(net.TCPNetwork, net.RateCalculator, History):	# RateCalculator actually uses payload size, but here payload is always the same size (one frame)
	def __init__(self, name, destination, data_event, history_length, *args, **kwargs):
		net.TCPNetwork.__init__(self, *args, **kwargs)		#, buffer_size, timeout
		net.RateCalculator.__init__(self, *args, **kwargs)	#, averaging_period, minimum_averaging_factor
		History.__init__(self, history_length)
		self.name = name
		self.destination = destination
		self.data_event = data_event
		self.feed_lock = threading.Lock()
		self.history = []
	def enqueue_data(self, data):
		if (data.get_flags() & input.Buffer.FLAG_BAD):	# Ignore bad frames (makes it look like no data is coming from feed)
			return
		with self.feed_lock:
			self.stats_history += [data]
			self.calculate_statistics(data.get_local_time())
			self.add_to_history(data)
			net.TCPNetwork.enqueue_data(self, data)
			self.data_event.set()
	def start(self, *args, **kwds):
		net.TCPNetwork.start(self, address=self.destination[0], port=self.destination[1], *args, **kwds)
	def get_ave_rate(self, calculate_now=True):
		with self.feed_lock:
			if calculate_now: self.calculate_statistics()
			return net.RateCalculator.get_ave_rate(self)
	def extract_frames(self, last_frame, next_frame, must_match=True):	# Non-inclusive
		with self.feed_lock:
			start_idx = self.in_history(last_frame)
			if start_idx == -1:
				if must_match:
					return []
			
			end_idx = self.in_history(next_frame)
			if end_idx == -1:
				end_idx = len(self.get_history())
			
			return self.get_history()[start_idx+1:end_idx]

class FeedThread(threading.Thread, History):
	def __init__(self, feeds, server, options, data_event, history_length, log, *args, **kwds):
		threading.Thread.__init__(self, *args, **kwds)
		History.__init__(self, history_length)
		self.feeds = feeds
		self.server = server
		self.options = options
		self.log = log
		self.data_event = data_event
		self.keep_running = True
		self.lock = threading.RLock()
		self.active_feed = feeds[0]
		self.active_feed_changed = False
		self.reset()
	def reset(self):
		self.next_best = None
		self.next_best_start = None
	def stop(self):
		self.keep_running = False
		self.data_event.set()
		self.join()
	def run(self):
		while self.keep_running:
			self.data_event.wait()
			self.data_event.clear()
			
			if not self.keep_running:
				break
			
			with self.lock:
				rates = []
				for feed in self.feeds:
					if feed.thread.connected:
						rate = feed.get_ave_rate()
					else:
						rate = 0
					if feed == self.active_feed: active_feed_rate = rate
					rates += [(feed, rate)]
				
				if len(self.feeds) > 1:
					rates = sorted(rates, key=lambda x: x[1], reverse=True)
					
					if (rates[0][1] > rates[1][1]):	# Skip if rate is the same (e.g. 0)
						highest_rate_feed = rates[0][0]
						
						if highest_rate_feed == self.active_feed:
							self.next_best = None
						else:
							if self.next_best == highest_rate_feed:
								next_best_delta = datetime.datetime.now() - self.next_best_start
								if next_best_delta.total_seconds() >= self.options.switch_wait_time:
									self.switch(highest_rate_feed)
							else:
								self.next_best = highest_rate_feed
								self.next_best_start = datetime.datetime.now()
								if active_feed_rate < (rates[0][1] * self.options.imm_switch_factor):
									self.switch(highest_rate_feed)
				
				frames = self.active_feed.get_data()
				if len(frames) > 0:
					if self.active_feed_changed:
						cnt = 0
						idx = -1
						for frame in frames:
							res = self.in_history(frame)
							if res > -1:	# This frame has already been sent (new active feed is running late)
								if ((idx + 1) != cnt):
									pass	# FIXME: Discontinuity in matches
								idx = cnt
							cnt += 1
						if idx > -1:
							self.log.log("Skipping %d old frames new feed" % (idx+1))
						frames = frames[idx+1:]
						
						if len(frames) > 0 and idx == -1 and len(self.get_history()) > 0:	# New active feed might be ahead of previous one, so prepend missing to current frame list
							last_sent = self.get_history()[-1]
							next_frame = frames[0]
							residual = self.active_feed.extract_frames(last_sent, next_frame)
							if len(residual) > 0:
								self.log.log("Copying %d frames from new feed's history" % (len(residual)))
								frames = residual + frames
						
						if len(frames) > 0:
							self.active_feed_changed = False
					
					for frame in frames:
						original = frame.get_original()
						idx = original.find('\n')
						original = original[:idx] + (" from %s" % self.active_feed.name) + original[idx:] + '\n\n'
						self.server.send(original)
						self.add_to_history(frame)
				
				for feed in self.feeds:
					if feed == self.active_feed:
						continue
					feed.get_data()	# Empty their buffers
	def switch(self, feed):
		with self.lock:
			self.reset()
			self.active_feed = feed
			self.active_feed_changed = True
			self.log.log("Switched to '%s'" % (self.active_feed.name))

class Log():
	def __init__(self, print_it=False, print_only=False):
		self.buffer = []
		self.lock = threading.Lock()
		self.print_it = print_it
		self.print_only = print_only
	def log(self, msg):
		if self.print_it:
			print msg
			if self.print_only:
				return
		with self.lock:
			self.buffer += [msg]
	def get_buffer(self):
		with self.lock:
			buffer = self.buffer
			self.buffer = []
			return buffer

def main():
	parser = OptionParser(usage="%prog: [options] name,address[:port] ...")
	
	parser.add_option("-p", "--port", type="int", default=net._PORT, help="default upstream port [default=%default]")
	parser.add_option("-l", "--listen", type="int", default=12876, help="default server listen port [default=%default]")
	parser.add_option("-b", "--buffer-size", type="int", default=1024*4, help="receive buffer size [default=%default]")
	parser.add_option("-L", "--limit", type="int", default=-1, help="async send buffer limit (-1: unlimited) [default=%default]")
	parser.add_option("-B", "--blocking-send", action="store_true", default=False, help="disable async send thread [default=%default]")
	parser.add_option("-w", "--switch-wait-time", type="float", default=5.0, help="time to wait until switching to superior feed [default=%default]")
	parser.add_option("-a", "--ave-period", type="float", default=10.0, help="rate averaging window [default=%default]")
	parser.add_option("-A", "--min-ave-factor", type="float", default=0.25, help="averaging window fullness [default=%default]")
	parser.add_option("-i", "--imm-switch-factor", type="float", default=0.75, help="immediate switch factor (percentage of superior's rate underwhich active must be) [default=%default]")
	parser.add_option("-u", "--update-interval", type="float", default=0.25, help="UI update interval [default=%default]")
	parser.add_option("-H", "--history-length", type="float", default=30.0, help="sent frame history length (s) [default=%default]")
	parser.add_option("", "--disable-ui", action="store_true", default=False, help="disable UI [default=%default]")
	
	(options, args) = parser.parse_args()
	
	if len(args) == 0:
		print "Supply at least one feed source"
		return
	
	feeds = []
	data_event = threading.Event()
	
	max_name_length = 0
	max_destination_length = 0
	for arg in args:
		parts = arg.split(",")
		if len(parts) < 2:
			print "Ignoring invalid feed source:", arg
			continue
		destination = parts[1]
		idx = destination.find(':')
		if idx > -1:
			destination = (destination[:idx], int(destination[idx+1:]))
		else:
			destination = (destination, options.port)
		max_name_length = max(max_name_length, len(parts[0]))
		max_destination_length = max(max_destination_length, len("%s:%d" % (destination[0], destination[1])))
		feeds += [FeedSource(
			name=parts[0],
			destination=destination,
			data_event=data_event,
			averaging_period=options.ave_period,
			minimum_averaging_factor=options.min_ave_factor,
			history_length=options.history_length
		)]	# buffer_size, timeout
	
	if len(feeds) == 0:
		print "No valid feeds"
		return
	
	server = None
	scr = None
	ex = None
	feed_thread = None
	ex_str = ""
	ui_timeout = 10	#ms	# MAGIC
	log = Log(options.disable_ui, options.disable_ui)
	
	try:
		server = tcp_server.ThreadedTCPServer(("", options.listen), buffer_size=options.buffer_size, blocking_mode=options.blocking_send, send_limit=options.limit, silent=not options.disable_ui)
		
		def _log_listen_retry(e, msg):
			print "    Socket error:", msg
			if (e == 98):
				print "    Waiting, then trying again..."
		
		server.start(retry=True, wait=LISTEN_RETRY_INTERVAL, log=_log_listen_retry)
		
		print "==> TCP server running in thread:", server.server_thread.getName()
		
		print "Starting feeds..."
		for feed in feeds:
			feed.start()	# Feeds will automatically reconnect if connection fails
		
		feed_thread = FeedThread(
			feeds=feeds,
			server=server,
			options=options,
			data_event=data_event,
			history_length=options.history_length,
			log=log
		)
		
		print "Starting feed thread..."
		feed_thread.start()
		
		################################
		
		if options.disable_ui:
			while True:
				raw_input()
		else:
			scr = curses.initscr()
			scr.timeout(ui_timeout)	# -1 for blocking
			scr.keypad(1)	# Otherwise app will end when pressing arrow keys
			curses.noecho()
			scr.erase()
			
			max_y, max_x = None, None
			
			while True:
				try:
					_max_y, _max_x = scr.getmaxyx()
					if _max_y != max_y or _max_x != max_x:
						scr.erase()
					
					max_y, max_x = _max_y, _max_x
					
					scr.move(0, 0)
					scr.clrtoeol()
					scr.addstr(str(datetime.datetime.now()))
					
					y = 2
					for feed in feeds:
						x = 0
						scr.move(y, x)
						scr.clrtoeol()
						if feed == feed_thread.active_feed:
							scr.addstr(">>>")
						elif feed == feed_thread.next_best:
							scr.addstr(" > ")
						
						x = 4
						scr.move(y, x)
						scr.addstr(feed.name)
						x += max_name_length+3
						
						scr.move(y, x)
						scr.clrtoeol()
						scr.addstr("%s:%d" % (feed.destination[0], feed.destination[1]))
						x += max_destination_length+3
						
						scr.move(y, x)
						scr.clrtoeol()
						scr.addstr("%04d" % (len(feed.stats_history)))
						x += 7
						
						scr.move(y, x)
						scr.clrtoeol()
						scr.addstr("%.0f" % (feed.get_ave_rate(calculate_now=False)))
						
						y += 1
						x = 0
						scr.move(y, x)
						scr.clrtoeol()
						scr.addstr(feed.get_status_string())
						
						y += 1
						
						y += 1
					
					log_buffer = log.get_buffer()
					if len(log_buffer) > 0:
						for log_msg in log_buffer[::-1]:
							scr.move(y, 0)
							scr.insertln()
							scr.addstr(log_msg)
							#y += 1
					
					scr.refresh()
					
					ch = scr.getch()
					if ch > -1:
						if ch == 27:	# ESC (quit)
							break
						elif ch >= ord('0') and ch <= ord('9'):
							idx = (ch - ord('0') - 1) % 10
							if idx < len(feeds):
								feed_thread.switch(feeds[idx])
				except:
					pass
				
				time.sleep(options.update_interval)
	except KeyboardInterrupt:
		pass
	except Exception, e:
		ex = e
		ex_str = traceback.format_exc()
	
	if scr:
		scr.erase()
		scr.refresh()
		
		curses.nocbreak()
		scr.keypad(0)
		curses.echo()
		curses.endwin()
	
	if ex:
		print "Unhandled exception:", ex
		if len(ex_str) > 0: print ex_str
	
	try:
		print "Shutting down..."
		
		if server:
			def _log_shutdown(client):
				print "Disconnecting client:", client.client_address
			
			server.shutdown(True, log=_log_shutdown)
		
		if feed_thread:
			print "Stopping feed thread..."
			feed_thread.stop()
		
		print "Stopping feeds..."
		for feed in feeds:
			feed.stop()
	except Exception, e:
		print "Unhandled exception during shutdown:", e
	
	return 0

if __name__ == '__main__':
	main()
