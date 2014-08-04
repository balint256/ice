#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  io.py
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

import datetime, os

class Buffer():
	FLAG_NONE	= 0x00
	FLAG_DROP	= 0x01
	FLAG_LAST	= 0x02
	FLAG_FIRST	= 0x04
	FLAG_BAD	= 0x08
	def __init__(self, buffer, flags=FLAG_NONE, time=None, original=None):
		self.buffer = buffer
		self.original = original
		self.flags = flags
		local_time_now = datetime.datetime.now()
		if time is None:
			time = local_time_now
		self.time = time
		self.local_time = local_time_now
	def get_buffer(self): return self.buffer
	def get_time(self): return self.time
	def get_flags(self): return self.flags
	def get_local_time(self): return self.local_time
	def get_original(self): return self.original

class Input():
	def __init__(self, *args, **kwds):
		self.buffers = []
		self.exception = None
		self.last_enqueue_time = None
	def start(self, *args, **kwds):
		self.exception = None
		return True
	def run(self):
		pass
	def stop(self):
		pass
	def enqueue_data(self, data):
		self.buffers += [data]
		self.last_enqueue_time = datetime.datetime.now()
	def get_data(self):
		buffers = self.buffers
		self.buffers = []
		return buffers
	def get_time_diff(self):
		return datetime.timedelta(0)
	def get_status_string(self):
		return ""

class PKParser():
	HEADER = "Frame"
	BAD = "(bad)"
	def __init__(self):
		self.reset()
	def reset(self):
		self.buffers = []
		self.line = ""
		self.original = []
		self.values = []
		self.frame_line_idx = None
		self.in_frame = False
		self.frame_number = None
		self.frame_time = None
		self.found_header = False
		self.bad_line_cnt = 0
		self.frame_cnt = 0
		self.last_log = ""
		self.frame_good = True
	def parse(self, data):
		self.line += str(data)
		
		lines = []
		while True:
			idx = self.line.find('\n')
			if idx == -1:
				break
			part = self.line[:idx].strip()
			lines += [part]
			self.line = self.line[idx+1:]
		
		for line in lines:
			found_header = False
			if not self.found_header:
				if len(line) > len(PKParser.HEADER) and line.find(PKParser.HEADER) == 0:
					self.found_header = found_header = True
				else:
					continue
			
			if found_header:
				self.last_log = line
				# FIXME:
				#self.frame_number
				#self.frame_time
				self.frame_good = (line.find(PKParser.BAD) == -1)
				self.frame_line_idx = 0
				self.values = []
				self.original = [line]
				continue
			elif self.frame_line_idx is not None:
				parts = line.split(" ")
				if len(parts) != 16:
					self.found_header = False
					self.bad_line_cnt += 1
					continue
				
				try:
					parts = map(lambda x: int(x, 16), parts)
				except:
					self.found_header = False
					self.bad_line_cnt += 1
					continue
				
				self.values += parts
				self.original += [line]
				
				self.frame_line_idx += 1
				
				if self.frame_line_idx == 8:
					if len(self.values) == 128:
						values = "".join(map(chr, self.values))
						flags = Buffer.FLAG_NONE
						if self.frame_cnt == 0:
							flags |= Buffer.FLAG_FIRST
						if not self.frame_good:
							flags |= Buffer.FLAG_BAD
						buffer = Buffer(values, flags=flags, time=self.frame_time, original="\n".join(self.original))
						self.buffers += [buffer]
						self.frame_cnt += 1
					else:
						self.bad_line_cnt += 1
					
					self.found_header = False
		
		return len(self.buffers) > 0
	def get_frames(self):
		buffers = self.buffers
		self.buffers = []
		return buffers

class FileInput(Input):
	def __init__(self, buffer_size=4096, *args, **kwds):
		Input.__init__(self, *args, **kwds)
		self.buffer_size = buffer_size
		self.f = None
		self.file_size = 0
		self.parser = PKParser()
		self.reset()
	def reset(self):
		self.bytes_read = 0
		self.file_path = None
	def start(self, file_path, *args, **kwds):
		Input.start(self, *args, **kwds)
		self.reset()
		self.file_size = os.path.getsize(file_path)
		self.f = open(file_path, 'r')
		self.file_path = file_path
		self.parser.reset()
	def stop(self):
		if self.f:
			self.f.close()
			self.f = None
		Input.stop(self)
	def get_data(self):
		while True:
			data = self.f.read(self.buffer_size)
			if len(data) == 0:
				return None
			self.bytes_read += len(data)
			if not self.parser.parse(data):
				continue	# Keep reading
			frames = self.parser.get_frames()
			for f in frames:
				self.enqueue_data(f)
			return self.buffers
	def get_status_string(self):
		if not self.f:
			return "No file open"
		return "Reading from: '%s' (%d/%d)" % (self.file_path, self.bytes_read, self.file_size)

def main():
	return 0

if __name__ == '__main__':
	main()
