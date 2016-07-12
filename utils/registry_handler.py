import labrad

class settingChannel(object):
    def __init__(
        self,
        ID,           # i
        name,         # s
        label,        # s
        description,  # s
        tags,         # *s
                      #
        channel,      # *s
        inputSlots,   # *i
        staticInputs, # *s
        inputUnits,   # *s
        staticUnits,  # *s
                      #
        minValue,     # *v
        maxValue,     # *v
        scale,        # *v
        offset,       # *v
        ):

        self.ID          = ID          # Channel ID. Must be unique. Can be used to access channel by ID alone.
        self.name        = name        # Channel name. Should be unique (not enforced.) Can be used to access channel, ID requried if not unique
        self.label       = label       # Label for axes when plotting or sweeping this channel
        self.description = description # Channel description (displayed when channel object is called alone)
        self.tags        = tags        # list of tags (strings) by which channels can be sorted and searched

        self.channel      = channel      # [deviceServer, device, setting]
        self.inputSlots   = inputSlots   # [int,  int,  ... ]    list of all input positions that must be specified when sending a request
        self.inputUnits   = inputUnits   # [unit, unit, ... ]    list of corresponding units for each input slot
        self.staticInputs = staticInputs # [value, value, ... ]  list of static inputs (stored as strings)
        self.staticUnits  = staticUnits  # [unit,  unit,  ... ]  list of corresponding units for each static input

        self.nStaticInputs    = len(self.staticInputs)
        self.nNonStaticInputs = len(self.inputSlots)
        self.nTotalInputs     = self.nStaticInputs+self.nNonStaticInputs 

        # lists of bound / scale information
        # If for a specific input slot they are set to None, they will be ignored. Use this for variable inputs of string type.
        self.minValue = minValue # Absolute minimum value to (ever) set this setting to
        self.maxValue = maxValue # Absolute maximum value to (ever) set this setting to
        self.scale    = scale    # Actual value set will be offset and scaled (offset first then scaled around the offset point)
        self.offset   = offset   # based on these values from the value the user specifies

    def __repr__(self):
        return """\nChannel ID  : %s\nChannel name: %s\n%s\n"""%(self.ID,self.name,self.description)

    def __str__(self):
        return """\nChannel ID  : %s\nChannel name: %s\n%s\n"""%(self.ID,self.name,self.description)

    def callSetting(self,inputs,connection,context=None,selectDevice=True):
        nInputs=len(inputs)
        if nInputs != self.nNonStaticInputs:raise ValueError("number of inputs does not match number of inptut slots")

        # if specified, select the device
        if selectDevice:
            if context != None: connection[self.channel[0]].select_device(self.channel[1],context=context)
            else              : connection[self.channel[0]].select_device(self.channel[1])

        # for zero inputs: just call the setting alone < setting() >
        if self.nTotalInputs == 0:
            if context != None:
                resp = connection[self.channel[0]][self.channel[2]](context=context)
            else:
                resp = connection[self.channel[0]][self.channel[2]]()
            return resp

        # convert inputs and static inptus to specified types
        _statics = [toType(self.staticInputs[pos], self.staticUnits[pos]) for pos in range(self.nStaticInputs)]
        _nonstat = [toType(inputs[pos],            self.inputUnits[pos] ) for pos in range(self.nNonStaticInputs)]

        # apply offset and scale, enforce bounds
        for pos in range(self.nNonStaticInputs):
            if self.scale[pos]    != None : _nonstat[pos] *= self.scale[pos]
            if self.offset[pos]   != None : _nonstat[pos] += self.offset[pos]
            if self.minValue[pos] != None :
                if _nonstat[pos] < self.minValue[pos]:
                    raise ValueError("Value deceeds minimum value <entry number: %s>, <minimum value: %s>, <value found: %s>, <offset: %s>, <scale: %s>"%(pos,self.minValue[pos],_nonstat[pos],self.offset[pos],self.scale[pos]))
                if _nonstat[pos] > self.maxValue[pos]:
                    raise ValueError("Value exceeds maximum value <entry number: %s>, <minimum value: %s>, <value found: %s>, <offset: %s>, <scale: %s>"%(pos,self.minValue[pos],_nonstat[pos],self.offset[pos],self.scale[pos]))

        # assemble input list
        assembly = assembleList(self.inputSlots,_nonstat,_statics)

        # for one input: call the setting with that value < setting(value) >
        if self.nTotalInputs == 1:
            if context != None:
                resp = connection[self.channel[0]][self.channel[2]](assembly[0],context=context)
            else:
                resp = connection[self.channel[0]][self.channel[2]](assembly[0])
            return resp

        # for multiple inputs, call the setting with the list of inputs < setting([inputs]) >
        else:
            if context != None:
                resp = connection[self.channel[0]][self.channel[2]](assembly,context=context)
            else:
                resp = connection[self.channel[0]][self.channel[2]](assembly)
            return resp

def toType(value,_type):
    #_type=_type.lower()
    if _type in ['string','str','s']  : return str(value)
    if _type in ['float','f','v']     : return float(value)
    if _type in ['integer','int','i'] : return int(value)
    return labrad.types.Value(value,_type)

def assembleList(inputSlots,inputs,statics):
    if len(inputSlots) != len(set(inputSlots)):
        raise ValueError("Error: duplicate positions in inputSlots")
    if len(inputSlots) != len(inputs):
        raise ValueError("Error: number of input slots does not match number of inputs")
    if not (max(inputSlots) < len(inputs+statics)):
        raise ValueError("Error: input slot requested higher than total number of slots")

    l   = []
    pos = 0
    inputPos  = 0
    staticPos = 0

    done = False
    while not done:
        if pos in inputSlots:
            l.append(inputs[inputPos])
            inputPos+=1
        else:
            l.append(statics[staticPos])
            staticPos+=1
        pos += 1
        if (inputPos>=len(inputs)) and (staticPos>=len(statics)):
            done = True
    return l

class registryHandler(object):

	channelLocation = ['','VDS','channels']

	def __init__(self,connection,context):
		self.connection = connection
		self.context    = context
		self.reg        = connection.registry

	def getAttrs(self,attr):
		prevDir = self.reg.cd(context=self.context)
		attrs   = []
		self.reg.cd(self.channelLocation,context=self.context)
		folders,files = self.reg.dir(context=self.context)
		for folder in folders:
			self.reg.cd(self.channelLocation+[folder],context=self.context)
			attrs.append(self.reg.get(attr,context=self.context))
		self.reg.cd(prevDir,context=self.context)
		return attrs

	def getFolderByAttr(self,attr,value):
		prevDir = self.reg.cd(context=self.context)
		appFolders = []
		self.reg.cd(self.channelLocation,context=self.context)
		folders,files=self.reg.dir(context=self.context)
		for folder in folders:
			self.reg.cd(self.channelLocation+[folder],context=self.context)
			fVal = self.reg.get(attr,context=self.context)
			if fVal == value:appFolders.append(folder)
		self.reg.cd(prevDir,context=self.context)
		return appFolders

	def delFolder(self,folder):
		prevDir = self.reg.cd(context=self.context)
		self.reg.cd(self.channelLocation+[folder],context=self.context)
		folders,files = self.reg.dir(context=self.context)
		for file in files:
			self.reg.del_(file,context=self.context)
		self.reg.cd(self.channelLocation,context=self.context)
		self.reg.rmdir(folder,context=self.context)
		self.reg.cd(prevDir,context=self.context)

	def getFolderByNameID(self,ID=None,name=None):
		if (ID==None) and (name==None):
			raise ValueError("ID and name cannot both be None: at least one must be specified")

		if ID!=None:
			byID = self.getFolderByAttr("ID",ID)
			if len(byID) == 0:
				raise ValueError("No channels match the ID (%s) given"%ID)
			if len(byID) > 1:
				raise ValueError("Multiple channels have the same ID (%s); this should not happen."%ID)
			byID=byID[0]

		if name!=None:
			byName = self.getFolderByAttr("name",name)
			if len(byName) == 0:
				raise ValueError("No channels match the name (%s) given"%name)
			if len(byName) > 1:
				raise ValueError("Multiple channels have the same name (%s); this should not happen. ")
			byName=byName[0]

		if (ID!=None) and (name!=None):
			if byID != byName:
				raise ValueError("The given ID (%s) and name (%s) do not match; they belong to <%s> and <%s> respectively."%(ID,name,byID,byName))

		if (ID != None):return byID
		return byName

	def writeChannelToRegistry(
		self,
        ID,           # i
        name,         # s
        label,        # s
        description,  # s
        tags,         # *s
                      #
        channel,      # *s
        inputSlots,   # *i
        staticInputs, # *s
        inputUnits,   # *s
        staticUnits,  # *s
                      #
        minValue,     # *v
        maxValue,     # *v
        scale,        # *v
        offset,       # *v
		):

		# go to channel storage location
		self.reg.cd(self.channelLocation,True,context=self.context)

		# check uniqueness of name and ID
		if ID   in self.getAttrs("ID")  : raise ValueError("ID specified is already taken.")
		if name in self.getAttrs("name"): raise ValueError("Name specified is already taken.")

		# create and go to folder for new channel
		entryName = "%s (%s)"%(ID,name)
		self.reg.cd(self.channelLocation+[entryName],True,context=self.context)

		# write informational attributes
		self.reg.set("name",        name,        context=self.context) # Write the name
		self.reg.set("ID",          ID,          context=self.context) # Write the ID
		self.reg.set("label",       label,       context=self.context) # Write the label
		self.reg.set("description", description, context=self.context) # Write the description
		self.reg.set("tags",        tags,        context=self.context) # write the tags

		# write the communication entries
		self.reg.set("channel",      channel,      context=self.context) # Write the cahnnel
		self.reg.set("inputSlots",   inputSlots,   context=self.context) #
		self.reg.set("inputUnits",   inputUnits,   context=self.context) #
		self.reg.set("staticInputs", staticInputs, context=self.context) #
		self.reg.set("staticUnits",  staticUnits,  context=self.context) #

		# write the bounds/scale/offset entries
		self.reg.set("minValue", minValue, context=self.context) #
		self.reg.set("maxValue", maxValue, context=self.context) #
		self.reg.set("scale",    scale,    context=self.context) #
		self.reg.set("offset",   offset,   context=self.context) #

	def removeChannelFromRegistry(self,ID=None,name=None):
		"""Removes a channel from the registry, specified by ID and/or name"""
		channel = self.getChannelByNameID(ID,name)
		self.delFolder(channel)

	def loadChannelByNameID(self,ID=None,name=None):
		channelFolder = self.getFolderByNameID(ID,name)
		return self.loadChannel(channelFolder)

	def loadChannel(self,channelFolder):
		"""Loads a channel from the registry to a settingChannel object"""

		# go to channel folder
		self.reg.cd(self.channelLocation+[channelFolder],context=self.context)

		ID          = self.reg.get("ID"         ,context=self.context)
		name        = self.reg.get("name"       ,context=self.context)
		label       = self.reg.get("label"      ,context=self.context)
		description = self.reg.get("description",context=self.context)
		tags        = self.reg.get("tags"       ,context=self.context)

		channel      = self.reg.get("channel"     ,context=self.context)
		inputSlots   = self.reg.get("inputSlots"  ,context=self.context)
		inputUnits   = self.reg.get("inputUnits"  ,context=self.context)
		staticInputs = self.reg.get("staticInputs",context=self.context)
		staticUnits  = self.reg.get("staticUnits" ,context=self.context)

		minValue = self.reg.get("minValue",context=self.context)
		maxValue = self.reg.get("maxValue",context=self.context)
		scale    = self.reg.get("scale"   ,context=self.context)
		offset   = self.reg.get("offset"  ,context=self.context)

		return settingChannel(ID,name,label,description,tags,channel,inputSlots,staticInputs,inputUnits,staticUnits,minValue,maxValue,scale,offset)

	def loadAllChannels(self):
		self.reg.cd(self.channelLocation,context=self.context)
		folders,files=self.reg.dir(context=self.context)
		channels = [self.loadChannel(channelFolder) for channelFolder in folders]
		return {ch.ID:ch for ch in channels},{ch.name:ch for ch in channels}

# if __name__ == '__main__':
# 	with labrad.connect() as cxn:

# 		# make registry handler with its own context
# 		r = registryHandler(cxn,cxn.context())

# 		# r.writeChannelToRegistry(
# 		# 	1,"AD5764 DCBox Eucalyptus Channel 1","DC1","Channel 1 of DCBOX AD5764 Eucalyptus",["test"],
# 		# 	['ad5764_dcbox','ad5764_dcbox (COM28)','set_voltage'],[1],[1],['f'],['i'],
# 		# 	[-1.0],[1.0],[0.001],[0.0],
# 		# 	)

# 		#dc0  = r.loadChannelByNameID(ID=0)
# 		#dc1  = r.loadChannelByNameID(ID=1)

# 		byID,byName = r.loadAllChannels()

# 		ctx0 = cxn.context()
# 		ctx1 = cxn.context()

# 		print(byID)
# 		print(byName)

# 		#byID[1].callSetting([675],cxn,ctx1)

# 		#dc0.callSetting([75],cxn,ctx0)
# 		#dc1.callSetting([125],cxn,ctx1)
