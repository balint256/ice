#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  elems_spinup.py
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

import lut, utils, res
from constants import *
from primitives import *
from elems_shared import *

import fss_angle, spin_rate

class PulseCountParser(Parser):
	def parse(self, l, *args, **kwds):
		cnt = 0
		val = 0
		for b in l:
			val <<= 1
			val |= b
			cnt += 1
			if cnt == 1:
				val <<= 3	# Pushes bit #1 out to 1 << 9: 1xxxxxx -> 1000xxxxxx
		return (True, val)

class TemperatureSupercomParser(ByteParser):
	pass	# FIXME: If supercom sync was working, would detect it and return appropriate value in series (would use element state arg to build series)

class ExternalFunctionParser(Parser):
	def __init__(self, fn, *args, **kwds):
		Parser.__init__(self, *args, **kwds)
		self.fn = fn
	def parse(self, val, *args, **kwds):
		try:
			return (True, self.fn(*val))
		except Exception, e:
			return (True, e)

class FSSAParser(Parser):
	def __init__(self, fn, *args, **kwds):
		Parser.__init__(self, *args, **kwds)
		self.fn = fn
	def parse(self, val, *args, **kwds):
	    # val will be list of bytes from AS1 (54-58)
	    # We also need 7 from AS2
		try:
			engine = kwds['state'].engine
			as2_tracker = engine.subcom_trackers[ANALOG_SUBCOM_2]
			byte7 = None
			if len(as2_tracker.subcom_frame) > 7:
				byte7 = as2_tracker.subcom_frame[7]
			elif len(as2_tracker.last_subcom_frame) > 7:
				byte7 = as2_tracker.last_subcom_frame[7]
			if byte7 is None:
				return (False, None)
			val += [byte7]
			return (True, self.fn(*val))
		except Exception, e:
			return (True, e)

firing_width_option_text	= ['invalid', '45 deg', '22.5 deg', '360 deg'];
enabled_option_text			= ['disabled', 'enabled']
on_option_text				= ['off', 'on']
complete_option_text		= ['incomplete', 'complete']
four_level_text				= ['off', 'low', 'medium', 'high']

_tlm_elements = [
	Element('frame counter',         name='Frame counter', desc='Index of minor frame', positions=[60]),
	Element('cmd_ctr_b',             positions=SubcomByteOffset(DIGITAL_SUBCOM, [20, 52])),
	Element('cmd_ctr_a',             positions=SubcomByteOffset(DIGITAL_SUBCOM, [21, 53])),
	
	Element('non_ess_current',       positions=ModeFilteredByteOffset({MODE_ENG: lut.combine_lut_dicts(lut.gen_lut_dict(85,  NUM_MINOR_FRAMES), lut.get_as2_lut(EMF_COLS, 44)), MODE_SCI: lut.get_as2_lut(SCI_COLS, 44)}), formatter=CurveFormatterValidator(curve=res.get_curve(32)), unit='A'),
	Element('28v_bus',               positions=ModeFilteredByteOffset({MODE_ENG: lut.combine_lut_dicts(lut.gen_lut_dict(86,  NUM_MINOR_FRAMES), lut.get_as2_lut(EMF_COLS, 43)), MODE_SCI: lut.get_as2_lut(SCI_COLS, 43)}), formatter=CurveFormatterValidator(curve=res.get_curve(41)), unit='V'),
	Element('ess_current',           positions=ModeFilteredByteOffset({MODE_ENG: lut.combine_lut_dicts(lut.gen_lut_dict(87,  NUM_MINOR_FRAMES), lut.get_as2_lut(EMF_COLS, 45)), MODE_SCI: lut.get_as2_lut(SCI_COLS, 45)}), formatter=CurveFormatterValidator(curve=res.get_curve(31)), unit='A'),
	Element('sa_current',            positions=ModeFilteredByteOffset({MODE_ENG: lut.combine_lut_dicts(lut.gen_lut_dict(101, NUM_MINOR_FRAMES), lut.get_as2_lut(EMF_COLS, 46)), MODE_SCI: lut.get_as2_lut(SCI_COLS, 46)}), formatter=CurveFormatterValidator(curve=res.get_curve(33)), unit='A'),
	Element('shunt_dump_current',    positions=SubcomByteOffset(ANALOG_SUBCOM_2, [47]),                                                                 formatter=CurveFormatterValidator(curve=res.get_curve(32)), unit='A'),
	
	Element('hps_1_thruster_select', positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(80,91)]), formatter=BinaryFormatter(fill=12)),
	Element('hps_1_sector_initiate', positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(92,101)])),
	Element('hps_1_sector_width',    positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(102,103)]), formatter=OptionFormatter(firing_width_option_text)),
	Element('hps_1_num_pulses',      positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(104,110)]), parser=PulseCountParser()),
	Element('hps_1_firing_ratio',    positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(111,114)])),
	Element('hps_1_ratio_select',    positions=SubcomBitOffset(DIGITAL_SUBCOM, [115]), formatter=OptionFormatter(enabled_option_text)),
	Element('hps_1_logic_pwr',       positions=SubcomBitOffset(DIGITAL_SUBCOM, [116]), formatter=OptionFormatter(on_option_text)),
	Element('hps_1_init_term',       positions=SubcomBitOffset(DIGITAL_SUBCOM, [117])),	#, formatter=OptionFormatter(binary_status_text)
	Element('hps_1_complete',        positions=SubcomBitOffset(DIGITAL_SUBCOM, [118]), formatter=OptionFormatter(complete_option_text)),
	Element('hps_1_28v_on',          positions=SubcomBitOffset(DIGITAL_SUBCOM, [119]), formatter=OptionFormatter(on_option_text)),
	
	Element('hps_2_thruster_select', positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(120,131)]), formatter=BinaryFormatter(fill=12)),
	Element('hps_2_sector_initiate', positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(132,141)])),
	Element('hps_2_sector_width',    positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(142,143)]), formatter=OptionFormatter(firing_width_option_text)),
	Element('hps_2_num_pulses',      positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(144,150)]), parser=PulseCountParser()),
	Element('hps_2_firing_ratio',    positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(151,154)])),
	Element('hps_2_ratio_select',    positions=SubcomBitOffset(DIGITAL_SUBCOM, [155]), formatter=OptionFormatter(enabled_option_text)),
	Element('hps_2_logic_pwr',       positions=SubcomBitOffset(DIGITAL_SUBCOM, [156]), formatter=OptionFormatter(on_option_text)),
	Element('hps_2_init_term',       positions=SubcomBitOffset(DIGITAL_SUBCOM, [157])),	#, formatter=OptionFormatter(binary_status_text)
	Element('hps_2_complete',        positions=SubcomBitOffset(DIGITAL_SUBCOM, [158]), formatter=OptionFormatter(complete_option_text)),
	Element('hps_2_28v_on',          positions=SubcomBitOffset(DIGITAL_SUBCOM, [159]), formatter=OptionFormatter(on_option_text)),
	
	#Element('HPS heaters command status', positions=BitOffset(bits=[,], lut=lut.get_ds_lut), formatter=BinaryFormatter(fill=2)),	# Each 1-bit from ds words 54 and 55
	Element('hps_1_prm_tk_htrs',     positions=SubcomBitOffset(DIGITAL_SUBCOM, [[432,440]]), formatter=OptionFormatter(four_level_text)),
	Element('hps_1_sec_tk_htrs',     positions=SubcomBitOffset(DIGITAL_SUBCOM, [[433,441]]), formatter=OptionFormatter(four_level_text)),
	Element('hps_2_prm_tk_htrs',     positions=SubcomBitOffset(DIGITAL_SUBCOM, [[434,442]]), formatter=OptionFormatter(four_level_text)),
	Element('hps_2_sec_tk_htrs',     positions=SubcomBitOffset(DIGITAL_SUBCOM, [[435,443]]), formatter=OptionFormatter(four_level_text)),
	Element('hps_1_2_prm_ln_htrs',   positions=SubcomBitOffset(DIGITAL_SUBCOM, [[436,444]]), formatter=OptionFormatter(four_level_text)),
	Element('hps_1_2_sec_ln_htrs',   positions=SubcomBitOffset(DIGITAL_SUBCOM, [[437,445]]), formatter=OptionFormatter(four_level_text)),
	
	Element('accel_pwr_monitor',     positions=SubcomByteOffset(ANALOG_SUBCOM_2, [3])),
	#Element('hps_1_tcX',              positions=lut.get_as2_lut(4), formatter=CurveFormatterValidator(curve=res.get_curve(63)), unit='C'),
	Element('hps_1_tc',              positions=SubcomByteOffset(ANALOG_SUBCOM_2, [4]), formatter=CurveFormatterValidator(curve=res.get_curve(63)), unit='C'),
	#Element('hps_2_tcX',              positions=lut.get_as2_lut(5), formatter=CurveFormatterValidator(curve=res.get_curve(64)), unit='C'),
	Element('hps_2_tc',              positions=SubcomByteOffset(ANALOG_SUBCOM_2, [5]), formatter=CurveFormatterValidator(curve=res.get_curve(64)), unit='C'),
	Element('hps_1_temp_supercom',   positions=SubcomByteOffset(ANALOG_SUBCOM_2, [39]), parser=TemperatureSupercomParser(), formatter=CurveFormatterValidator(curve=res.get_curve(45)), unit='C'), # note: this cycles through multiple temperature readings, but sync not as expected)
	Element('hps_2_temp_supercom',   positions=SubcomByteOffset(ANALOG_SUBCOM_2, [40]), parser=TemperatureSupercomParser(), formatter=CurveFormatterValidator(curve=res.get_curve(45)), unit='C'), # note: this cycles through multiple temperature readings, but sync not as expected)
	
	Element('spin_rate',             positions=SubcomByteOffset(DIGITAL_SUBCOM, [utils.num_range(34,35)]), parser=ExternalFunctionParser(spin_rate.spinrate)),
	Element('spin_period',           positions=SubcomByteOffset(DIGITAL_SUBCOM, [utils.num_range(34,35)]), parser=ExternalFunctionParser(spin_rate.spinperiod)),
	Element('mag_rate',              positions=SubcomByteOffset(DIGITAL_SUBCOM, [utils.num_range(38,39)]), parser=ExternalFunctionParser(spin_rate.magrate)),
	Element('mag_period',            positions=SubcomByteOffset(DIGITAL_SUBCOM, [utils.num_range(38,39)]), parser=ExternalFunctionParser(spin_rate.magperiod)),
	Element('spin_angle',            positions=SubcomByteOffset(DIGITAL_SUBCOM, [utils.num_range(32,35)]), parser=ExternalFunctionParser(spin_rate.spinangle)),
	
	#Element('fss_angle',             positions=ByteOffset(offsets=utils.num_range(54,58)+[7], lut=lut.get_as1_lut), parser=ExternalFunctionParser(fss_angle.fssangle)),
	#Element('fss_angle',             positions=SubcomByteOffset(ANALOG_SUBCOM_1, [utils.num_range(54,58)+[7]]), parser=ExternalFunctionParser(fss_angle.fssangle)),
	Element('fss_angle_a',           positions=SubcomByteOffset(ANALOG_SUBCOM_1, [utils.num_range(54,58)]), parser=FSSAParser(fss_angle.fssangle)),  # HACK
	Element('fss_angle_b',           positions=SubcomByteOffset(ANALOG_SUBCOM_2, [utils.num_range(59,63)+[8]]), parser=ExternalFunctionParser(fss_angle.fssangle)),
	
	Element('hps_1_tk_press',        positions=SubcomByteOffset(ANALOG_SUBCOM_2, [14]), formatter=CurveFormatterValidator(curve=res.get_curve(65)), unit='psi'),
	Element('hps_2_tk_press',        positions=SubcomByteOffset(ANALOG_SUBCOM_2, [15]), formatter=CurveFormatterValidator(curve=res.get_curve(65)), unit='psi'),
	
	Element('hps_1_lv_a',            positions=[61], parser=FixedWordParser(2, 2)),
	Element('hps_2_lv_b',            positions=[61], parser=FixedWordParser(2, 3)),
	Element('hps_1_lv_c',            positions=[61], parser=FixedWordParser(2, 4)),
	Element('hps_2_lv_d',            positions=[61], parser=FixedWordParser(2, 5)),
	
	Element('accelerometer',         positions=utils.flatten([x*16,x*16+8] for x in range(8)), formatter=CurveFormatterValidator(curve=res.get_curve(-1)), unit="m/s^2"),	# FIXME range/lambda
]

def get_elements():
	return _tlm_elements

def main():
	return 0

if __name__ == '__main__':
	main()
