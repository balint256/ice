#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  elems_test.py
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

# 'get_elements' must be defined and return list of 'Element's

import lut, utils, res
from constants import *
from primitives import *
from elems_shared import *

#gen_lut_fn = lambda x: lut.gen_lut_dict(x[0], NUM_MINOR_FRAMES, True)

lock_option_text = ['unlocked', 'locked']

_tlm_elements = [
	Element('FRMCNT', name='Frame counter', desc='Index of minor frame', positions=[60]),
	
	Element('CMDCNT1',  positions=lut.get_ds_lut([20, 52])),
	Element('CMDCNT1x', positions=SubcomByteOffset(DIGITAL_SUBCOM, [20, 52])),
	
	Element('CMDCNT2', positions=lut.get_ds_lut([21, 53])),
	Element('CMDCNT2x', positions=SubcomByteOffset(DIGITAL_SUBCOM, [21, 53])),
	
	Element('CMDCNT2b', positions=SubcomBitOffset(DIGITAL_SUBCOM, [utils.num_range(21*8,21*8+7), utils.num_range(53*8,53*8+7)])),
	
	#Element('CMDCNT2txt', positions=_gen_lut_with_emf_lut(_EMF_LUT, [21, 53])),
	#Element('CMDCNT12', positions=get_ds_lut(17, 64, [[20, 21], [52,53]])),
	
	Element('SYNC0', positions=[utils.num_range(123,127)], formatter=HexFormatter()),
#	Element('SYNC1', positions=ByteOffset(offsets=[utils.num_range(123,127)], lut=gen_lut_fn), formatter=BinaryFormatter()),
#	Element('SYNC2', positions=BitOffset(offsets=[utils.num_range(123*8,127*8+7)], lut=gen_lut_fn), formatter=BinaryFormatter()),
	
	#Element('PREV', positions=[[60, -(128-60)]]),	# FIXME
	#Element('BITS', bits={6: [range(400,404)]}),
	Element('spacecraft_clock',       positions=[utils.num_range(61,63)], parser=FixedWordParser(0)),
	Element('address_dec_a',          positions=[63], parser=FixedWordParser(2, 6)),
	Element('address_dec_b',          positions=[63], parser=FixedWordParser(2, 7)),
	Element('parity_dec_a',           positions=[63], parser=FixedWordParser(2, 4)),
	Element('parity_dec_b',           positions=[63], parser=FixedWordParser(2, 5)),
    Element('data_present_dec_a',     positions=[63], parser=FixedWordParser(2, 2)),
	Element('data_present_dec_b',     positions=[63], parser=FixedWordParser(2, 3)),
	Element('cmd_drivers_dec_a',      positions=[63], parser=FixedWordParser(2, 0)),
	Element('cmd_drivers_dec_b',      positions=[63], parser=FixedWordParser(2, 1)),
    Element('xpdr_a_lock',            positions=[62], parser=FixedWordParser(2, 4), formatter=OptionFormatter(lock_option_text)),	# Docs are wrong, this is correct
	Element('xpdr_b_lock',            positions=[62], parser=FixedWordParser(2, 5), formatter=OptionFormatter(lock_option_text)),	# Docs are wrong, this is correct
	
	Element('xpdr_a_signal_str',      positions=lut.get_as2_lut(58), formatter=CurveFormatterValidator(curve=res.get_curve(36)), unit='dBm'),
	Element('xpdr_b_signal_str',      positions=lut.get_as2_lut(49), formatter=CurveFormatterValidator(curve=res.get_curve(36)), unit='dBm'),
	Element('xpdr_a_static_phase_err',positions=lut.get_as2_lut(50), formatter=CurveFormatterValidator(curve=res.get_curve(36)), unit='kHz'),
	Element('xpdr_b_static_phase_err',positions=lut.get_as2_lut(51), formatter=CurveFormatterValidator(curve=res.get_curve(36)), unit='kHz'),
]

def get_elements():
	return _tlm_elements

def main():
	return 0

if __name__ == '__main__':
	main()
