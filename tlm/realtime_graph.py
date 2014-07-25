#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  realtime_graph.py
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
#   Detect window close (e.g. wx._core.PyDeadObjectError)
#   Replace horizontal line code with MPL's in-built one

import numpy
import matplotlib
import matplotlib.pyplot as pyplot

class realtime_graph():
    def __init__(self, title="Real-time Graph", sub_title="", x_range=None, show=False, parent=None, manual=False, pos=111, redraw=True, figsize=None, padding=None, y_limits=None, gui_timeout=0.1, data=None, x=None):
        self.parent = parent
        
        if isinstance(x_range, float) or isinstance(x_range, int):
            x_range = (0, x_range-1)
        
        self.title_text = title
        self.sub_title_text = sub_title
        self.x_range = x_range
        self.y_limits = y_limits
        
        self.figsize = figsize
        self.pos = pos
        self.padding = padding
        
        self.figure = None
        self.title = None
        #self.plot = None
        self.plots = []
        self.subplot = None # Axes
        self.points = []
        
        self._gui_timeout = gui_timeout
        
        self._horz_lines = []
        self._horz_lines_map = {}
        
        self._vert_lines = []
        self._vert_lines_map = {}
        
        if show:
            self._create_figure(data=data, x=x, manual=manual, redraw=redraw)
    
    def _create_figure(self, data=None, x=None, redraw=True, manual=False):
        if self.parent is None:
            pyplot.ion()    # Must be here
            
            kwds = {}
            if self.figsize is not None:
                kwds['figsize'] = self.figsize
            self.figure = pyplot.figure(**kwds)   # num=X
            
            if self.padding is not None:
                self.figure.subplots_adjust(**self.padding)
            
            self.title = self.figure.suptitle(self.title_text)
            if manual == False:
                self.subplot = self.figure.add_subplot(self.pos)
        else:
            self.subplot = self.parent.figure.add_subplot(self.pos)
        
        if self.subplot is not None:
            self.subplot.grid(True)
            self.subplot.set_title(self.sub_title_text)
            if x is None:
                #x = numpy.array([0])
                #if self.x_range is None and data is not None:
                #    self._calc_x_range(data)
                #if self.x_range is not None:
                #    x = numpy.linspace(self.x_range[0], self.x_range[1], self.x_range[1]-self.x_range[0])
                
                #pass
                
                if data is not None:
                    self._calc_x_range(data)
                    x = numpy.linspace(self.x_range[0], self.x_range[1], len(data[0]))
            else:
                self.x_range = (min(x), max(x)) # FIXME: Only if x_range is not None?
            
            #if data is None:
            #    data = numpy.array([0]*len(x))
            
            if not isinstance(data, list):
                data = [data]
            
            if data is not None and x is not None:
                #self.plot, = pyplot.plot(x, data)
                #self.plot, = self.subplot.plot(x, data)
                
                #self.plots += self.subplot.plot([(x, _y) for _y in data])  # FIXME
                for d in data:
                    self.plots += self.subplot.plot(x, d)
            
            # This was moved left one indent level ('_apply_axis_limits' is safe)
            
            #self.plot.axes.grid(True)
            #self.plot.axes.set_title(self.sub_title_text)
        
            #self.plot.axes.set_xlim([min(x),max(x)])
            self._apply_axis_limits()
        
        if redraw:
            self._redraw()
    
    def _apply_axis_limits(self):
        if self.x_range is not None:
            #self.plot.axes.set_xlim(self.x_range)
            self.subplot.set_xlim(self.x_range)
        if self.y_limits is not None:
            #self.plot.axes.set_ylim(self.y_limits)
            self.subplot.set_ylim(self.y_limits)
    
    def _calc_x_range(self, data):
        if isinstance(data, list):
            data = data[0]
        self.x_range = (0, len(data) - 1)
    
    def set_y_limits(self, y_limits):
        self.y_limits = y_limits
    
    def set_data(self, data, x=None, auto_x_range=True, x_range=None, autoscale=True, redraw=False):  # Added auto_x_range/x_range/autoscale before redraw
        if data is None:
            return
        elif not isinstance(data, list):
            data = [data]
        
        #self.figure.canvas.flush_events()
        
        if x_range is not None:
            self.x_range = x_range
        
        if self.x_range is None and data is not None:
            self._calc_x_range(data)
        
        if x is None:
            x = numpy.linspace(self.x_range[0], self.x_range[1], len(data[0]))
        elif auto_x_range and x_range is None:
            self.x_range = (min(x), max(x))
        
        cnt = 0
        for d in data:
            if cnt >= len(self.plots):
                self.plots += self.subplot.plot(x, d)
            else:
                self.plots[cnt].set_data(x, d)
            cnt += 1
        
        if autoscale:
            # All three are necessary!
            self.subplot.relim()
            self.subplot.autoscale_view()
            #self.plot.axes.set_xlim(self.x_range)
            self._apply_axis_limits()
        
        if self.x_range is not None:
            for line in self._horz_lines:    # FIXME: Use line.get_data()
                line_x, line_y = line.get_data()
                value = line_y[0]
                line.set_data(numpy.array([self.x_range[0], self.x_range[1]]), numpy.array([value, value]))
        
        if self.y_limits is not None:
            for line in self._vert_lines:    # FIXME: Use line.get_data()
                line_x, line_y = line.get_data()
                value = line_x[0]
                line.set_data(numpy.array([value, value]), numpy.array([self.y_limits[0], self.y_limits[1]]))
        
        if redraw:
            self._redraw()
    
    def update(self, data=None, title=None, sub_title=None, x=None, auto_x_range=True, x_range=None, autoscale=True, points=None, clear_existing_points=True, redraw=True):
        if title is not None:
            self.set_title(title)
        if sub_title is not None:
            self.set_sub_title(sub_title)
        if self.parent is None and self.figure is None:
            self._create_figure(data=data, x=x, redraw=False)   # FIXME: 'auto_x_range', 'x_range'
        elif data is not None:
            self.set_data(data=data, x=x, auto_x_range=auto_x_range, x_range=x_range)
        if points is not None:
            if clear_existing_points:
                self.clear_points()
            self.add_points(points)
        if redraw:
            self._redraw()
    
    def clear_points(self, redraw=False):
        for line in self.points:
            self.subplot.lines.remove(line)
        self.points = []
        if redraw:
            self._redraw()
    
    def add_points(self, points, marker='mo', redraw=False):
        if len(points) == 0:
            return
        self.points += self.subplot.plot(numpy.array(map(lambda x: x[0], points)), numpy.array(map(lambda x: x[1], points)), marker)    # FIXME: Better way to do this?
        if redraw:
            self._redraw()
    
    def redraw(self):
        self._redraw()
    
    def _redraw(self, quick=False):
        if self.parent is None:
            try:
                if self.figure is None:
                    self._create_figure(redraw=False)
                self.figure.canvas.draw()
                self.figure.canvas.flush_events()
                if quick == False:
                    self.figure.canvas.start_event_loop(timeout=self._gui_timeout)
                self.figure.canvas.flush_events()
            except RuntimeError:
                self._create_figure()
        else:
            self.parent._redraw(quick=quick)
    
    def run_event_loop(self, timeout=None):
        if timeout is None:
            timeout = self._gui_timeout
        self.figure.canvas.start_event_loop(timeout=timeout)
    
    def go_modal(self):
        if self.figure is None:
            return False
        return self.figure.canvas.start_event_loop()
    
    def set_title(self, title, redraw=False):
        self.title_text = title
        if self.title is not None:
            self.title.set_text(title)
            if redraw:
                self._redraw()
    
    def set_sub_title(self, sub_title, redraw=False):
        self.sub_title_text = sub_title
        if self.subplot is not None:
            self.subplot.set_title(sub_title)
            #self.plot.axes.set_title(self.sub_title_text)  # Same
            if redraw:
                self._redraw()
    
    def add_horz_line(self, value, color='red', linestyle='-', id=None, replace=True, redraw=False):
        if id in self._horz_lines_map.keys():
            if not replace:
                return
            self.remove_horz_line(id)
        line = matplotlib.lines.Line2D(numpy.array([self.x_range[0], self.x_range[1]]), numpy.array([value, value]), linestyle=linestyle, color=color)
        self._horz_lines += [line]
        if id is not None:
            self._horz_lines_map[id] = line
        self.subplot.add_line(line)
        if redraw:
            self._redraw()
    
    def remove_horz_line(self, id):
        if not id in self._horz_lines_map.keys():
            return
        line = self._horz_lines_map[id]
        self._horz_lines.remove(line)
        self.subplot.lines.remove(line)
        del self._horz_lines_map[id]
    
    def add_vert_line(self, value, color='black', linestyle='-', id=None, replace=True, redraw=False):
        if id in self._vert_lines_map.keys():
            if not replace:
                return
            self.remove_vert_line(id)
        if self.y_limits is None:
            return
        line = matplotlib.lines.Line2D(numpy.array([value, value]), numpy.array([self.y_limits[0], self.y_limits[1]]), linestyle=linestyle, color=color)
        self._vert_lines += [line]
        if id is not None:
            self._vert_lines_map[id] = line
        self.subplot.add_line(line)
        if redraw:
            self._redraw()
    
    def remove_vert_line(self, id):
        if not id in self._vert_lines_map.keys():
            return
        line = self._vert_lines_map[id]
        self._vert_lines.remove(line)
        self.subplot.lines.remove(line)
        del self._vert_lines_map[id]
    
    def save(self, output_name):
        if self.parent is not None:
            return self.parent.save(output_name)
        self.figure.savefig(output_name)
        return True

def main():
	# FIXME: Plot something simple
	return 0

if __name__ == '__main__':
	main()
