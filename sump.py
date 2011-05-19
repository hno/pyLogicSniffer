# -*- coding: ASCII -*-
'''Interface with SUMP logic-analyzer device.
Copyright 2011, Mel Wilson mwilson@melwilsonsoftware.ca

This file is part of pyLogicSniffer.

    pyLogicSniffer is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    pyLogicSniffer is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with pyLogicSniffer.  If not, see <http://www.gnu.org/licenses/>.
'''

import serial, sys
import numpy as np
SUMP_BAUD = 115200
SUMP_PATH = '/dev/ttyACM0'

class SumpError (StandardError): '''Errors raised by the SUMP client.'''
class SumpIdError (SumpError): '''The wrong string was returned by an ID request.'''
class SumpFlagsError (SumpError): '''Illegal combination of flags.'''
class SumpTriggerEnableError (SumpError): '''Illegal trigger enable setting.'''
class SumpStageError (SumpError): '''Illegal trigger stage setting.'''
	
class SumpDeviceSettings (object):
	'''Sampling and trigger parameters.'''
	clock_rate = 100000000	# undivided clock rate, in Hz, from testing with OBLS
	
	def __init__ (self):
		self.default()
		
	def default (self):
		'''Non-impossible default settings.'''
		# general settings ..
		self.divider = 2			# default sampling rate 100MHz
		self.read_count = 4096		# default sampling size
		self.delay_count = 2048		# default before/after 50/50
		self.inverted = False
		self.external = False
		self.filter = False
		self.demux = False
		self.channel_groups = 0x0	# default all channel groups
		
		self.trigger_enable = 'None'
		# trigger settings, by stage ..
		self.trigger_mask = [0]*4
		self.trigger_values = [0]*4
		self.trigger_delay = [0]*4
		self.trigger_level = [0]*4
		self.trigger_channel = [0]*4
		self.trigger_serial = [False]*4			# default parallel trigger testing
		self.trigger_start = [True] + [False]*3	# default immediate start
		
	def clone (self):
		'''Clone an independent copy of these settings.'''
		o = SumpDeviceSettings()	# other instance
		self.copy (o)
		return o
		
	def copy (self, other):
		'''Copy these settings to another instance.'''
		other.divider = self.divider
		other.read_count = self.read_count
		other.delay_count = self.delay_count
		other.inverted = self.inverted 
		other.external = self.external
		other.filter = self.filter
		other.demux = self.demux
		other.channel_groups = self.channel_groups
		other.trigger_mode = self.trigger_mode
		
		# trigger settings, by stage ..
		other.trigger_mask[:] = self.trigger_mask
		other.trigger_values[:] = self.trigger_values
		other.trigger_delay[:] = self.trigger_delay
		other.trigger_level[:] = self.trigger_level
		other.trigger_channel[:] = self.trigger_channel
		other.trigger_serial[:] = self.trigger_serial
		other.trigger_start[:] = self.trigger_start
		other.trigger_enable = self.trigger_enable
		
	def get_sample_rate (self):
		'''Return the sample rate called for by these settings.'''
		rate = int (self.clock_rate / self.divider)
		if self.demux:
			rate *= 2
		return rate
		

class SumpInterface (object):
	clock_rate = 100000000	# undivided clock rate, in Hz, from testing with OBLS
	protocol_version = '1.0'
	
	def __init__ (self, path, baud=SUMP_BAUD):
		self.port = serial.Serial (path, baud)
		self.reset()
		
	def reset (self):
		w = self.port.write
		w ('\x00')
		w ('\x00')
		w ('\x00')
		w ('\x00')
		w ('\x00')
		
	def capture (self, settings):
		'''Request a capture.'''
		read_count = settings.read_count
		d = self.data = np.zeros ( (read_count,), dtype=np.uint32)
		mask = settings.channel_groups
		read = self.port.read
		def reading ():
			'''Get a 32-bit small-endian reading from the analyzer.'''
			v = 0
			if not (mask & 1):	v |= ord (read(1))
			if not (mask & 2):	v |= ord (read(1)) << 8
			if not (mask & 4):	v |= ord (read(1)) << 16
			if not (mask & 8):	v |= ord (read(1)) << 24
			return v
		sys.stderr.write ('reading %d\n'% (read_count,)); sys.stderr.flush()
		self.port.write ('\x01')
		for i in xrange (read_count-1, -1, -1):	# readings arrive most-recent-first
			d[i] = reading()
			#~ sys.stderr.write ('%d: %x\t' % (i, d[i],)); sys.stderr.flush()
		self.reset()
		return d
		
	def id_string (self):
		'''Return device's SUMP ID string.'''
		self.port.write ('\x02')
		val = self.port.read (4)	# 4 bytes as a small-endian int
		return val[::-1]
		
	def xon (self):
		self.port.write ('\x11')
		
	def xoff (self):
		self.port.write ('\x13')
		
	def _trace_control (self, legend, w=None):
		if w is None:
			w = self.port.write
		print '\n' + legend + ' \t',
		def tw (data):
			print '%02x' % (ord (data),),
			w (data)
		return tw
		
	def _send_trigger_mask (self, stage, mask):
		#~ w = self.port.write
		w = self._trace_control ('Trigger mask')
		w (chr (0xC0 | (stage << 2)))
		w (chr (mask & 0xFF))
		w (chr ((mask >> 8) & 0xFF))
		w (chr ((mask >> 16) & 0xFF))
		w (chr ((mask >> 24) & 0xFF))
		
	def send_trigger_mask_settings (self, settings):
		#~ w = self.port.write
		w = self._trace_control ('Trigger mask')
		for stage in xrange (4):
			m = settings.trigger_mask[stage]
			w (chr (0xC0 | (stage << 2)))
			w (chr (m & 0xFF))
			w (chr ((m >> 8) & 0xFF))
			w (chr ((m >> 16) & 0xFF))
			w (chr ((m >> 24) & 0xFF))
			
	def _send_trigger_values (self, stage, values):
		#~ w = self.port.write
		w = self._trace_control ('Trigger values')
		w (chr (0xC1 | (stage << 2)))
		w (chr (values & 0xFF))
		w (chr ((values >> 8) & 0xFF))
		w (chr ((values >> 16) & 0xFF))
		w (chr ((values >> 24) & 0xFF))
		
	def send_trigger_values_settings (self, settings):
		#~ w = self.port.write
		w = self._trace_control ('Trigger values')
		for stage in xrange (4):
			v = settings.trigger_values[stage]
			w (chr (0xC1 | (stage << 2)))
			w (chr (v & 0xFF))
			w (chr ((v >> 8) & 0xFF))
			w (chr ((v >> 16) & 0xFF))
			w (chr ((v >> 24) & 0xFF))
			
	def _send_trigger_configuration (self, stage, delay, channel, level, start, serial):
		#~ w = self.port.write
		w = self._trace_control ('Trigger config')
		w (chr (0xC2 | (stage << 2)))
		d = delay
		w (chr (d & 0xFF))
		w (chr ((d >> 8) & 0xFF))
		c = channel
		w (chr (((c & 0x0F) << 4) | level) )
		w (chr ((start << 3) | (serial << 2) | ((c & 0x10) >> 4)))
		
	def send_trigger_configuration_settings (self, settings):
		#~ w = self.port.write
		w = self._trace_control ('Trigger config')
		for stage in xrange (4):
			w (chr (0xC2 | (stage << 2)))
			d = settings.trigger_delay[stage]
			w (chr (d & 0xFF))
			w (chr ((d >> 8) & 0xFF))
			c = settings.trigger_channel[stage]
			w (chr (((c & 0x0F) << 4) | settings.trigger_level[stage]) )
			w (chr ((settings.trigger_start[stage] << 3) | (settings.trigger_serial[stage] << 2) | ((c & 0x10) >> 4)))
		
	def send_divider_settings (self, settings):
		#~ w = self.port.write
		w = self._trace_control ('Divider')
		w ('\x80')
		d = settings.divider - 1	# offset 1 correction for SUMP hardware
		w (chr (d & 0xFF))
		w (chr ((d >> 8) & 0xFF))
		w (chr ((d >> 16) & 0xFF))
		w ('\x00')
		
	def send_read_and_delay_count_settings (self, settings):
		#~ w = self.port.write
		w = self._trace_control ('Read/Delay')
		w ('\x81')
		r = (settings.read_count + 3) >> 2	# factor 4 correction for SUMP hardware
		w (chr (r & 0xFF))
		w (chr ((r >> 8) & 0xFF))
		d = (settings.delay_count + 3) >> 2	# factor 4 correction for SUMP hardware
		w (chr (d & 0xFF))
		w (chr ((d >> 8) & 0xFF))
		
	def send_flags_settings (self, settings):
		#~ w = self.port.write
		w = self._trace_control ('Flags')
		w ('\x82')
		w (chr ((settings.inverted << 7) 
				| (settings.external << 6) 
				| (settings.channel_groups << 2)
				| (settings.filter << 1)
				| settings.demux
			))
		w ('\x00')	# enable RLE compression, alternate number scheme, test modes
		w ('\x00')
		w ('\x00')
		
	def send_settings (self, settings):
		self.send_divider_settings (settings)
		self.send_read_and_delay_count_settings (settings)
		self.send_flags_settings (settings)
		trigger_enable = settings.trigger_enable
		if trigger_enable == 'None':
			# send always-trigger trigger settings
			for stage in xrange (4):
				self._send_trigger_configuration (stage, 0, 0, 0, True, False)
				self._send_trigger_mask (stage, 0)
				self._send_trigger_values (stage, 0)
		elif trigger_enable == 'Simple':
			# set settings from stage 0, no-op for stages 1..3
			self._send_trigger_configuration (0, settings.trigger_delay[0], settings.trigger_channel[0], 0, True, settings.trigger_serial[0])
			self._send_trigger_mask (0, settings.trigger_mask[0])
			self._send_trigger_values (0, settings.trigger_values[0])
			for stage in xrange (1, 4):
				self._send_trigger_configuration (stage, 0, 0, 0, False, False)
				self._send_trigger_mask (stage, 0)
				self._send_trigger_values (stage, 0)
		elif trigger_enable == 'Complex':
			self.send_trigger_configuration_settings (settings)
			self.send_trigger_mask_settings (settings)
			self.send_trigger_values_settings (settings)
		else:
			raise SumpTriggerEnableError
			
	def query_meta_data (self):
		result = []
		self.reset()
		r = self.port.read
		self.port.write (0x04)
		data = []
		while True:
			c = r (1)
			if not c:		# end-of-file
				break
			if not ord (c):		# binary 0 end-of-metadata marker
				break
			data.append (c)
		while data:
			token = ord (data.pop (0))
			if token <= 0x1F:	# C-string follows token
				x = data.index (chr (0))
				if x < 0:
					v = ''.join (data)
					data[:] = []
				else:
					v = ''.join (data[:x])
					data[:x+1] = []
				result.append ( (token, v) )
				
			elif token <= 0x3F:	# 32-bit int follows token
				v = (ord (data[0]) << 24) | (ord (data[1]) << 16) | (ord (data[2]) << 8) | ord (data[3])
				data[:4] = []
				result.append ( (token, v) )
				
			elif token <= 0x5F:	# 8-bit int follows token
				result.append ( (token, ord (data.pop (0))) )
				
			else:
				result.append ( (token, None) )
		return result
				
		
	def close (self):
		self.port.close()
		self.port = None
