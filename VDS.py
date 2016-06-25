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

class VirtualDeviceServer(LabradServer):
	"""DESC_TEXT"""

	name = 'Virtual Device Server'
	channelLocation = ['','VDS','channels']

	@inlineCallbacks
	def initServer(self):
		self.reg = self.client.registry # Easier registry access
		yield self.initRegistry()       # Make sure the necessary registry structure is there

		yield self.getChannelsFromRegistry() # Read all the channel info from the registry

	@inlineCallbacks
	def getChannelsFromRegistry(self):
		"""Fetches all the channel info stored in the registry"""
		self.channels = yield {}                # initiate channel info dict
		yield self.reg.cd(self.channelLocation) # go to channel location
		folders,files = yield self.reg.dir()
		for channel in folders:
			yield self.fetchChannelInfo(channel)
		#print(self.channels)

	@inlineCallbacks
	def fetchChannelInfo(self,channel):
		"""Updates self.channels with an entry for specified channel"""
		yield self.reg.cd(self.channelLocation+[channel])
		ch_name = yield self.reg.get('name')
		ch_ID   = yield self.reg.get('ID')
		ch_server,ch_device,ch_setting = yield self.reg.get('channel')
		yield self.channels.update([
			[channel,{'name':ch_name,'ID':ch_ID,'server':ch_server,'device':ch_device,'setting':ch_setting}]
			])

	@inlineCallbacks
	def initRegistry(self):
		"""Ensures that the registry has the appropriate location for channel information"""
		dirCreated = False
		for step in range(1,len(self.channelLocation)):
			yield self.reg.cd(self.channelLocation[:step])
			folders,files = yield self.reg.dir()
			if not (self.channelLocation[step] in folders):
				yield self.reg.mkdir(self.channelLocation[step])
				dirCreated = True
		if dirCreated:
			print("The registry directory has just been created.")
			print("The full directory is %s"%str(self.channelLocation))
			print("If this isn't the first time this server has")
			print("been run then there may be something wrong.")



	@setting(1,"Add Channel",
		ID          = 's',
		name        = 's',
		label       = 's',
		description = 's',
		tags        = '*s',

		channel           = '*s',
		settingInputSlot  = 'i',
		#settingInputUnits = '*s',
		staticInputs      = '*s',
		#staticInputsUnits = '*s',

		minValue   = 'v',
		maxValue   = 'v',
		scale      = 'v',
		offset     = 'v',

		returns = 'b{success}')
	def addChannel(self,c,ID,name,label,description,tags,channel,settingInputSlot,staticInputs,minValue,maxValue,scale,offset):
		yield self.reg.cd(self.channelLocation) # go to channel location
		folders,files = yield self.reg.dir()

		entryName = "%s (%s)"%(ID,name) # entry name is "ID (name)"
		if entryName in folders:        # check that it doesn't already exist
			print("Tried to make a channel that already exists.")
			print("name: %s; ID: %s"%(name,ID))
			returnValue(False)

		# if it doesn't exist already, continue...
		yield self.reg.mkdir(entryName) # create the folder
		yield self.reg.cd(entryName)    # go to the new folder

		# Informational entries: channel name, ID, description, etc
		yield self.reg.set("name",name)               # Write the name
		yield self.reg.set("ID",ID)                   # Write the ID
		yield self.reg.set("label",label)             # Write the label
		yield self.reg.set("description",description) # Write the description
		yield self.reg.set("tags",tags)               # write the tags

		# Communication entries: These determine how the setting corresponding to this channel is called
		yield self.reg.set("channel",channel)                   # [server, device, setting] : specifies what setting this channel corresponds to
		yield self.reg.set("settingInputSlot",settingInputSlot) # For multiple-input settings, this specifies which input is the varied input
		yield self.reg.set("staticInputs",staticInputs)         # [input,input,...] All the non-varied inputs. Do not leave a space/empty entry for the varied input.

		# Units will be determined upon first use of the channel
		#yield self.reg.set("inputUnits",inputUnits)             # The LabRAD data type for the varied input
		
		# Input range entries: These determine the min/max values & scaling/offset behaviour of the varied input
		yield self.reg.set("minValue",minValue) # Minimum (real) value. Minimum value AFTER offset & scale are applied
		yield self.reg.set("maxValue",maxValue) # Maximum (real) value. Maximum value AFTER offset & scale are applied
		yield self.reg.set("offset",offset)     # Offset paramater. Applied before scaling.
		yield self.reg.set("scale",scale)       # Scaling parameter. Applied after offset.

		# Now add the new channel's info to self.channels
		self.fetchChannelInfo(entryName)

		# If we got this far it was a success, so return True
		returnValue(True)
		
	@setting(2,"Delete Channel",ID='s',name='s',returns='b{success}')
	def delChannel(self,c,ID,name):
		yield self.reg.cd(self.channelLocation) # Go to channel location
		folders,files = yield self.reg.dir()

		entryName = "%s (%s)"%(ID,name) # entry name is "ID (name)"
		if not (entryName in folders):
			print("Error: tried to delete a channel that doesn't exist.")
			returnValue(False)

		yield self.reg.cd(entryName)
		subFolders,subFiles = yield self.reg.dir()
		if len(subFolders) > 0:
			print("Error: found folders inside channel regsitry object.")
			print("There should not be folders inside the channel registry object.")
			returnValue(False)

		for key in subFiles:         # Now we delete all the keys
			yield self.reg.del_(key) # so that we can remove the folder

		yield self.reg.cd(self.channelLocation) # Go back to the folder location
		yield self.reg.rmdir(entryName)         # Remove the folder

		# Now we're done, so return True 
		returnValue(True)

	@setting(100,"Get Channels",returns='*s')
	def getChannels(self,c):
		channels = yield self.channels.keys()
		returnValue(channels)

	#@setting(101,"Get Channel Info",)


__server__ = VirtualDeviceServer()
if __name__ == '__main__':
	from labrad import util
	util.runServer(__server__)
