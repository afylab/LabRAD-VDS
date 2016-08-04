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
version = 0.3
description = Virtual Device Server for LabRAD. Handles dedicated output channels
[startup]
cmdline = %PYTHON% %FILE%
timeout = 20
[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

from labrad.server import LabradServer, setting, Signal
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value

###########################
## ChannelInstance class ##
###########################
class ChannelInstance(object):
	def __init__(
		self,

		context,

		ID,
		name,
		label,
		description,
		tags,

		has_get,
		has_set,

		get_setting,
		get_inputs,
		get_inputs_units,

		set_setting,
		set_var_slot,
		set_var_units,
		set_statics,
		set_statics_units,
		set_min,
		set_max,
		set_offset,
		set_scale,

		):

			self.context = context

			self.ID		  = ID
			self.name		= name
			self.label	   = label
			self.description = description
			self.tags		= tags

			self.has_get = has_get
			self.has_set = has_set

			self.get_setting	  = get_setting
			self.get_inputs	   = get_inputs
			self.get_inputs_units = get_inputs_units

			self.set_setting	   = set_setting
			self.set_var_slot	  = set_var_slot
			self.set_var_units	 = set_var_units
			self.set_statics	   = set_statics
			self.set_statics_units = set_statics_units
			self.set_min		   = set_min
			self.set_max		   = set_max
			self.set_offset		= set_offset
			self.set_scale		 = set_scale

	def __repr__(self):
		return """Channel Instance Object with < ID:{ID} name:{name} >\n\n{description}""".format(ID=self.ID,name=self.name,description=self.description)
	def __str__(self):
		return """Channel Instance Object with < ID:{ID} name:{name} >\n\n{description}""".format(ID=self.ID,name=self.name,description=self.description)

###############################
## Formatting/data functions ##
###############################
def to_type(value,type_):
	if type_.startswith('.'):return Value(value,type_[1:])
	if type_ in ['string','str','s']  : return str(value)
	if type_ in ['float','f','v']	 : return float(value)
	if type_ in ['integer','int','i'] : return int(value)
	return Value(value,_type)

def assemble_set_list(set_var_slot,set_var_value,set_statics):
	if set_var_slot > len(set_statics):raise ValueError("Variable slot ({set_var_slot}) higher than highest input slot ({h_slot})".format(set_var_slot=set_var_slot,h_slot=len(set_statics)))
	ret = []
	ret += set_statics[:set_var_slot]
	ret += [set_var_value]
	ret += set_statics[set_var_slot:]
	return ret

class VirtualDeviceServer(LabradServer):
	"""
	Virtual Device Server.
	Handles usage of dedicated channels
	"""

	name             = 'virtual_device_server'                 # server name (as appears in pylabrad connections)
	channel_location = ['','virtual_device_server','channels'] # registry location of channel information
	none_types       = ['none','-','']                         # these strings will be interpreted as <None> by the VDS

	channels_by_id   = {} # These start out empty
	channels_by_name = {} # And will be populated on server init

	sPrefix = 704000
	signal__reg_channel_added   = Signal(sPrefix+0,"signal__reg_channel_added" , "*s") # Activated when a new channel is added; parameters = [ID,name]
	signal__reg_channel_deleted = Signal(sPrefix+1,"signal__reg_chanel_deleted", "*s") # Activated when a channel is deleted  ; parameters = [ID,name]
	signal__channel_set         = Signal(sPrefix+2,"signal__channel_set"       , "*s") # Activated when a channel is set      ; parameters = [ID,name,response]
	signal__channel_get         = Signal(sPrefix+3,"signal__channel_get"       , "(ssv)") # Activated when a channel is gotten   ; parameters = [ID,name,response]

	@inlineCallbacks
	def initServer(self):
		self.reg         = self.client.registry  # more convenient connection to the registry
		self.reg_context = self.client.context() # context for registry operations
		yield self.registry_setup()              # set up the registry directory if it hasn't been already
		self.channels_by_id,self.channels_by_name = yield self.load_all_channels()

	#######################
	## Registry handling ##
	#######################
	
	@inlineCallbacks
	def registry_setup(self):

		yield self.reg.cd(self.channel_location,True,context=self.reg_context)

	@inlineCallbacks
	def get_attributes(self,attribute):
		"""Gets a list of all channels' values for a specified attribute"""
		prev_dir = yield self.reg.cd(context=self.reg_context)
		attrs	= []
		yield self.reg.cd(self.channel_location,context=self.reg_context)
		folders,files = yield self.reg.dir(context=self.reg_context)
		for folder in folders:
			yield self.reg.cd(self.channel_location+[folder],context=self.reg_context)
			attr = yield self.reg.get(attribute,context=self.reg_context)
			attrs.append(attr)
		yield self.reg.cd(prev_dir,context=self.reg_context)
		returnValue(attrs)

	@inlineCallbacks
	def get_folders_by_attribute(self,attribute,value):
		"""Find a channel by its value for a particular attribute"""
		prev_dir = yield self.reg.cd(context=self.reg_context)
		attr_folders = []
		yield self.reg.cd(self.channel_location,context=self.reg_context)
		folders,files=yield self.reg.dir(context=self.reg_context)
		for folder in folders:
			yield self.reg.cd(self.channel_location+[folder],context=self.reg_context)
			fval = yield self.reg.get(attribute,context=self.reg_context)
			if fval == value:attr_folders.append(folder)
		yield self.reg.cd(prev_dir,context=self.reg_context)
		returnValue( attr_folders )

	@inlineCallbacks
	def del_folder(self,folder_loc,recur=False):
		"""Removes a folder & its keys. If recur is set to True, recursively removes subfolders & subfolder keys."""
		if type(folder_loc) != type([]):folder_loc=[folder_loc]
		prev_dir = yield self.reg.cd(context=self.reg_context)
		yield self.reg.cd(self.channel_location+folder_loc,context=self.reg_context)
		folders,files = yield self.reg.dir(context=self.reg_context)
		for folder in folders:
			if recur:
				yield self.del_folder(folder_loc+[folder],True)
			else:
				pass
		for file in files:
			yield self.reg.del_(file,context=self.reg_context)
		yield self.reg.cd(self.channel_location+folder_loc[:-1],context=self.reg_context)
		yield self.reg.rmdir(folder_loc[-1],context=self.reg_context)
		try:
			yield self.reg.cd(prev_dir,context=self.reg_context)
		except:
			yield self.reg.cd(self.channel_location,context=self.reg_context)

	@inlineCallbacks
	def get_folder_by_id_name(self,ID=None,name=None):
		"""Get the name of a folder by specifying its name and/or ID
		Must specify at least one of name,ID
		If both are specified, they must point to the same folder
		"""
		yield

		if (ID==None) and (name==None):
			raise ValueError("ID and name cannot both be None: at least one must be specified")

		if ID!=None:
			byID = yield self.get_folders_by_attribute("ID",ID)
			if len(byID) == 0:
				raise ValueError("No channels match the ID (%s) given"%ID)
			if len(byID) > 1:
				raise ValueError("Multiple channels have the same ID (%s); this should not happen."%ID)
			byID=byID[0]

		if name!=None:
			byName = yield self.get_folders_by_attribute("name",name)
			if len(byName) == 0:
				raise ValueError("No channels match the name (%s) given"%name)
			if len(byName) > 1:
				raise ValueError("Multiple channels have the same name (%s); this should not happen. ")
			byName=byName[0]

		if (ID!=None) and (name!=None):
			if byID != byName:
				raise ValueError("The given ID (%s) and name (%s) do not match; they belong to <%s> and <%s> respectively."%(ID,name,byID,byName))

		if (ID != None):returnValue( byID )
		returnValue( byName )

	@inlineCallbacks
	def write_channel_to_registry(
		self,
		ID,
		name,
		label,
		description,
		tags,

		has_get,
		has_set,

		get_setting,
		get_inputs,
		get_inputs_units,

		set_setting,
		set_var_slot,
		set_var_units,
		set_statics,
		set_statics_units,
		set_min,
		set_max,
		set_offset,
		set_scale,

		):

		prev_dir = yield self.reg.cd(context=self.reg_context)
		yield self.reg.cd(self.channel_location,True,context=self.reg_context)

		# create and go to folder for new channel
		entryName = "%s (%s)"%(ID,name)
		yield self.reg.cd(self.channel_location+[entryName],True,context=self.reg_context)

		# informational attributes
		yield self.reg.set("name",        name,        context=self.reg_context) # Write the name
		yield self.reg.set("ID",          ID,          context=self.reg_context) # Write the ID
		yield self.reg.set("label",       label,       context=self.reg_context) # Write the label
		yield self.reg.set("description", description, context=self.reg_context) # Write the description
		yield self.reg.set("tags",        tags,        context=self.reg_context) # write the tags

		yield self.reg.set("has_get",     has_get,     context=self.reg_context)
		yield self.reg.set("has_set",     has_set,     context=self.reg_context)

		# <get> folder
		yield self.reg.cd(self.channel_location+[entryName,"get"],True,context=self.reg_context)
		yield self.reg.set("setting",      get_setting,      context=self.reg_context)
		yield self.reg.set("inputs",       get_inputs,       context=self.reg_context)
		yield self.reg.set("inputs_units", get_inputs_units, context=self.reg_context)

		# <set> folder
		yield self.reg.cd(self.channel_location+[entryName,"set"],True,context=self.reg_context)
		yield self.reg.set("setting",       set_setting,       context=self.reg_context)
		yield self.reg.set("var_slot",      set_var_slot,      context=self.reg_context)
		yield self.reg.set("var_units",     set_var_units,     context=self.reg_context)
		yield self.reg.set("statics",       set_statics,       context=self.reg_context)
		yield self.reg.set("statics_units", set_statics_units, context=self.reg_context)
		yield self.reg.set("min",           set_min,           context=self.reg_context)
		yield self.reg.set("max",           set_max,           context=self.reg_context)
		yield self.reg.set("offset",        set_offset,        context=self.reg_context)
		yield self.reg.set("scale",         set_scale,         context=self.reg_context)

		yield self.reg.cd(prev_dir,context=self.reg_context)

	@inlineCallbacks
	def del_channel_from_registry(self,ID=None,name=None):
		"""Removes a channel from the registry"""
		folder = yield self.get_folder_by_id_name(ID,name)
		yield self.del_folder(folder,True)

	@inlineCallbacks
	def load_channel_by_id_name(self,ID=None,name=None):
		"""Loads info from the registry to a channel object"""
		channel_folder = yield self.get_folder_by_id_name(ID,name)
		channel        = yield self.load_channel(channel_folder)
		returnValue(channel)

	@inlineCallbacks
	def load_channel(self,channel_folder):
		"""Loads a channel from the registry to a ChannelInstance object"""

		prev_dir = yield self.reg.cd(context=self.reg_context)
		yield self.reg.cd(self.channel_location+[channel_folder],context=self.reg_context)

		# informational stuff
		ID          = yield self.reg.get("ID",          context=self.reg_context)
		name        = yield self.reg.get("name",        context=self.reg_context)
		label       = yield self.reg.get("label",       context=self.reg_context)
		description = yield self.reg.get("description", context=self.reg_context)
		tags        = yield self.reg.get("tags",        context=self.reg_context)
		has_get     = yield self.reg.get("has_get",     context=self.reg_context)
		has_set     = yield self.reg.get("has_set",     context=self.reg_context)

		# <get> folder
		yield self.reg.cd(self.channel_location+[channel_folder,"get"],context=self.reg_context)
		get_setting      = yield self.reg.get("setting",      context=self.reg_context)
		get_inputs       = yield self.reg.get("inputs",       context=self.reg_context)
		get_inputs_units = yield self.reg.get("inputs_units", context=self.reg_context)
		get_inputs = [to_type(get_inputs[n],get_inputs_units[n]) for n in range(len(get_inputs))] # convert get_inputs to specified types


		# <set> folder
		yield self.reg.cd(self.channel_location+[channel_folder,"set"],context=self.reg_context)
		set_setting       = yield self.reg.get("setting",       context=self.reg_context)
		set_var_slot      = yield self.reg.get("var_slot",      context=self.reg_context)
		set_var_units     = yield self.reg.get("var_units",     context=self.reg_context)
		set_statics       = yield self.reg.get("statics",       context=self.reg_context)
		set_statics_units = yield self.reg.get("statics_units", context=self.reg_context)
		set_min	          = yield self.reg.get("min",           context=self.reg_context)
		set_max           = yield self.reg.get("max",           context=self.reg_context)
		set_offset        = yield self.reg.get("offset",        context=self.reg_context)
		set_scale         = yield self.reg.get("scale",         context=self.reg_context)
		set_statics = [to_type(set_statics[n],set_statics_units[n]) for n in range(len(set_statics))] # convert statics to specified types

		set_min    = yield self.bound_interp(set_min   ) # These are stored as strings in the regsitry
		set_max    = yield self.bound_interp(set_max   ) # but we need them to be <None> if appropriate
		set_offset = yield self.bound_interp(set_offset) # or floats. bound_interp converts "none" or empty
		set_scale  = yield self.bound_interp(set_scale ) # strings to <None>, and otherwise to floats.

		yield self.reg.cd(prev_dir,context=self.reg_context)

		channel = ChannelInstance(
			self.client.context(),              # a unique context for this channel
			ID, name, label, description, tags, # informational attributes
			has_get, has_set,                   # has_get & has_set
			get_setting, get_inputs, get_inputs_units, # <GET> info
			set_setting, set_var_slot, set_var_units,  # <SET> info
			set_statics, set_statics_units,            # <SET> info
			set_min, set_max, set_offset, set_scale,   # <SET> info
			)

		returnValue(channel)

	@inlineCallbacks
	def load_all_channels(self):
		"""Loads all channels from registry & returns dicts by ID & by name"""
		prev_dir = yield self.reg.cd(context=self.reg_context)
		yield self.reg.cd(self.channel_location,context=self.reg_context)
		folders,files = yield self.reg.dir(context=self.reg_context)
		channels = []
		for channel_folder in folders:

			try:
				channel = yield self.load_channel(channel_folder)
				channels.append(channel)
			except:
				print("Found invalid folder: {channel_folder}; deleting it".format(channel_folder=channel_folder))
				yield self.del_folder(channel_folder,True)

		yield self.reg.cd(prev_dir,context=self.reg_context)
		returnValue([{channel.ID:channel for channel in channels},{channel.name:channel for channel in channels}])

	@inlineCallbacks
	def bound_interp(self,bound):
		"""Converts none-interpretable strings into None types, and all other strings to floats"""
		low = yield bound.lower()
		if low in self.none_types:
			returnValue(None)
		else:
			returnValue(float(bound))

	#######################
	## Channel functions ##
	#######################

	@inlineCallbacks
	def get_channel_by_id_name(self,ID=None,name=None):
		"""Returns a channel specified by name and/or ID"""
		yield
		if not ID  : ID   = None
		if not name: name = None
		if (ID == None) and (name == None):raise ValueError("ID and name can't both be None or empty")

		if not (ID is None):
			try:
				by_id = self.channels_by_id[ID]
			except:
				raise ValueError("Invalid ID: {ID}; does not correspond to any channel.".format(ID=ID))
		if not (name is None):
			try:
				by_name = self.channels_by_name[name]
			except:
				raise ValueError("Invalid name: {name}; does not correspond to any channel.".format(name=name))

		if ID == None:        # If user only specifies name,
			channel = by_name # get channel by the name.
		elif name == None:    # If user only specifies ID,
			channel = by_id   # get channel by the ID.
		else:                 # If user specifies both, make sure they both validly point to the same channel.
			if by_id.ID   != by_name.ID   : raise ValueError("Name and ID point to different channels. If both specified they must point to the same channel.")
			if by_id.name != by_name.name : raise ValueError("Name and ID point to different channels. If both specified they must point to the same channel.")
			channel = by_id   # now that we know they point to the same channel, just set it to by_id

		returnValue(channel)

	##############
	## Settings ##
	##############

	@setting(1,"reg add channel",
		ID                = 's',
		name              = 's',
		label             = 's',
		description       = 's',
		tags	          = '*s',
		has_get           = 'b',
		has_set           = 'b',
		get_setting       = '*s',
		get_inputs        = '*s',
		get_inputs_units  = '*s',
		set_setting       = '*s',
		set_var_slot      = 'i',
		set_var_units     = 's',
		set_statics       = '*s',
		set_statics_units = '*s',
		set_min           = 's',  # These will end up as either floats or <None>
		set_max           = 's',  # But to allow for either they are strings
		set_offset        = 's',  # The strings must be interpretable as either
		set_scale         = 's',  # floats or None types.

		returns = 'b{success}')
	def reg_add_channel(self, c, ID, name, label, description, tags, has_get, has_set, get_setting, get_inputs, get_inputs_units, set_setting, set_var_slot, set_var_units, set_statics, set_statics_units, set_min, set_max, set_offset, set_scale):
		"""Adds a new channel to the regsitry.\nDoes not override; to overwrite, first delete the old channel."""

		# make sure ID is valid
		try:
			if int(ID) < 0:raise ValueError("ID specified is negative. Was {ID}, must be non-negative integer.".format(ID=ID))
		except:
			raise ValueError("ID specified is invalid. Was {ID}, must be non-negative integer.".format(ID=ID))


		# check that name and ID aren't taken
		IDs   = yield self.get_attributes("ID")
		names = yield self.get_attributes("name")
		if ID   in IDs  : raise ValueError("ID specified is already taken.")
		if name in names: raise ValueError("Name specified is already taken.")

		# check that all values in [min,max,scale,offset] are correctly interpretable
		for inst in [set_min,set_max,set_offset,set_scale]:
			if inst.lower() in self.none_types:continue
			try:
				float(inst)
			except:
				raise ValueError("Value ({isnt}) for minValue,maxValue,scale,offset not interpetable as either float or NoneType".format(inst=inst))

		# write the channel entry
		yield self.write_channel_to_registry(ID,name,label,description,tags,has_get,has_set,get_setting,get_inputs,get_inputs_units,set_setting,set_var_slot,set_var_units,set_statics,set_statics_units,set_min,set_max,set_offset,set_scale)

		# Now load & add the new channel
		channel = yield self.load_channel_by_id_name(ID = ID)
		self.channels_by_id.update([   [ID,   channel] ])
		self.channels_by_name.update([ [name, channel] ])

		# done & succesful
		self.signal__reg_channel_added([ID,name])
		returnValue(True)

	@setting(2,"reg del channel",ID='s',name='s',returns='b{success}')
	def reg_del_channel(self,c,ID,name):
		"""Deletes a channel specified by name, ID, or both"""
		if not ID  : ID   = None
		if not name: name = None

		if (ID == None) and (name == None):raise ValueError("Error: <ID> and <name> cannot both be None or empty")

		if ID   == None: ID   = self.channels_by_name[name].ID
		if name == None: name = self.channels_by_id[ID].name

		yield self.del_channel_from_registry(ID,name)

		del self.channels_by_name[name]
		del self.channels_by_id[ID]	

		self.signal__reg_chanel_deleted([ID,name])
		returnValue(True)

	@setting(100,"list channels",returns='**s')
	def list_channels(self,c):
		"""Returns a list of all channels in the registry in the form [ [ID,name], [ID,name], ... ]"""
		keys = yield self.channels_by_id.keys()
		returnValue([ [str(key),self.channels_by_id[key].name] for key in keys])

	#@setting(101,"list active channels",returns='**s')
	#def list_active_channel(self,c):
	#	yield

	#@setting(102,"channel details",ID='s',name='s',returns='**s')
	#def channel_details(self,c,ID,name):
	#	"""Returns the details of a given channel in the form of a list [ [attribute, value], [attribute, value], ... ]"""
	#	channel = yield self.get_channel_by_id_name(ID,name)

	@setting(1000,"set channel",ID='s',name='s',value='v',returns='s{response}')
	def set_channel(self,c,ID,name,value):
		"""Set the output of a channel. \nChanel specified by name and/or ID. \nOutput specified by value"""

		# How do we tell if a channel is active? Corresponding server, and corresponding device
		# Error if accesing inactive channel?
		# Setting for getting a list of active channels as opposed to all channels?
		# 
		# Should get and set both have server & device
		# or should server & device be shared, and get/set only specify settings?
		# for now assume server & device are the same between get & set
		# could cause problems (wrong thing being set) if set & get have different devices, as set & get share the same context
		
		channel = yield self.get_channel_by_id_name(ID,name)

		if not channel.has_set:
			raise ValueError("Tried to set_channel on a channel that does not support set commands")

		set_var_value = (value * channel.set_scale) + channel.set_offset
		if set_var_value > channel.set_max:raise ValueError("value set (raw:{value}, adjusted:{set_var_value}) exceeds max value:{max}".format(value=value,set_var_value=set_var_value,max=channel.set_max))
		if set_var_value < channel.set_min:raise ValueError("value set (raw:{value}, adjusted:{set_var_value}) deceeds min value:{min}".format(value=value,set_var_value=set_var_value,min=channel.set_min))

		if len(channel.set_statics) == 0:
			try: # first we try to send the setting in the channel's context.
				ret = yield self.client[channel.set_setting[0]][channel.set_setting[2]](set_var_value,context=channel.context)
			except: # if it fails we try selecting the device & sending the request again
				yield self.client[channel.set_setting[0]].select_device(channel.set_setting[1],context=channel.context)
				ret = yield self.client[channel.set_setting[0]][channel.set_setting[2]](set_var_value,context=channel.context)
				# if it fails here we don't catch it, as it failed for a reason other than
				# not being selected, and we want the user to see the error message.
		else:
			inputs = assemble_set_list(channel.set_var_slot,set_var_value,channel.set_statics)
			try:
				ret = yield self.client[channel.set_setting[0]][channel.set_setting[2]](inputs,context=channel.context)
			except:
				yield self.client[channel.set_setting[0]].select_device(channel.set_setting[1],context=channel.context)
				ret = yield self.client[channel.set_setting[0]][channel.set_setting[2]](inputs,context=channel.context)

		self.signal__channel_set([channel.ID,channel.name,str(ret)])
		returnValue(str(ret))

	@setting(1001,"get channel",ID='s',name='s',returns='v{value}')
	def get_channel(self,c,ID,name):
		"""Gets the value (input or set output) of a channel. \nChannel specified by name and/or ID"""
		channel = yield self.get_channel_by_id_name(ID,name)
		if not channel.has_get:
			raise ValueError("Tried to get_channel on a channel that does not support get commands")

		if len(channel.get_inputs) == 0: # If there are no inputs required, then 
			try:                         # we call the setting with context only (no inputs)
				ret = yield self.client[channel.get_setting[0]][channel.get_setting[2]](context=channel.context)
			except:
				yield self.client[channel.get_setting[0]].select_device(channel.get_setting[1],context=channel.context)
				ret = yield self.client[channel.get_setting[0]][channel.get_setting[2]](context=channel.context)

		elif len(channel.get_inputs) == 1: # If there's exactly one input required then
			try:                           # we call the setting with (input, context)
				ret = yield self.client[channel.get_setting[0]][channel.get_setting[2]](channel.get_inputs[0],context=channel.context)
			except:
				yield self.client[channel.get_setting[0]].select_device(channel.get_setting[1],context=channel.context)
				ret = yield self.client[channel.get_setting[0]][channel.get_setting[2]](channel.get_inputs[0],context=channel.context)

		else:    # multiple inputs required, then they can be given as a list
			try: # so we call the setting with ([inputs...], context)
				ret = yield self.client[channel.get_setting[0]][channel.get_setting[2]](channel.get_inputs,context=channel.context)
			except:
				ret = yield self.client[channel.get_setting[0]][channel.get_setting[2]](channel.get_inputs,context=channel.context)
				yield self.client[channel.get_setting[0]].select_device(channel.get_setting[1],context=channel.context)

		self.signal__channel_get([channel.ID,channel.name,float(ret)])
		returnValue(float(ret))



__server__ = VirtualDeviceServer()
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
