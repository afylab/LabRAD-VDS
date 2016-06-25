# Copyright []
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
### BEGIN NODE INFO
[info]
name = Virtual Device Server
version = 1.0
description = Virtual Device Server for LabRAD. Handles dedicated output channels
[startup]
cmdline = %PYTHON% %FILE%
timeout = 20
[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

from labrad.server import LabradServer, setting
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value

class VDS(LabradServer):
	"""DESC_TEXT"""

	name = 'Virtual Device Server'
	channelLocation = ['','VDS','channels']

	@inlineCallbacks
	def initServer(self):
		self.reg = self.client.registry # Easier registry access
		yield self.initRegistry()       # Make sure the necessary registry structure is there

	@inlineCallbacks
	def initRegistry(self):
		"""Ensures that the registry has the appropriate location for channel information"""
		for step in range(1,len(self.channelLocation)-1):
			yield self.reg.cd(self.channelLocation[:step])
			folders,files = yield self.reg.dir()
			if not (self.channelLocation[step] in folders):
				yield self.reg.mkdir(self.channelLocation[step])



	@inlineCallbacks
	def addChannel(self,args):
		pass

	@inlineCallbacks
	def delChannel(self,args):
		pass