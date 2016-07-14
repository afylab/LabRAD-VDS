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

class serverInfo(object):
    name = 'virtual_device_server'

    serverNameAD5764_ACBOX      = 'ad5764_acbox'
    serverNameAD5764_DCBOX      = 'ad5764_dcbox'
    serverNameAD5780_QUAD_DCBOX = 'dcbox_quad_ad5780'

    deviceNameAD5764_ACBOX      = '{serverName} ({port})' # these are to be formatted with the .format() command
    deviceNameAd5764_DCBOX      = '{serverName} ({port})' # with the arguments (serverName, port)
    deviceNameAd5780_QUAD_DCBOX = '{serverName} ({port})' # when the VDS needs to know the device name





from labrad.server import LabradServer, setting
from twisted.internet.defer import inlineCallbacks, returnValue
import labrad.units as units
from labrad.types import Value

############################
## Setting Channel object ##
############################
class settingChannel(object):
    def __init__(
        self,
        ID,           # s
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
    return Value(value,_type)
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


class VirtualDeviceServer(LabradServer):
    """Virtual Device Server.\nHandles usage of dedicated channels"""
    info            = serverInfo()
    name            = info.name
    channelLocation = ['','VDS','channels']
    noneTypes       = ['none','-','']

    @inlineCallbacks
    def initServer(self):
        self.reg     = self.client.registry
        self.context = self.client.context()
        yield self.registrySetup()
        self.channelsByID, self.channelsByName = yield self.loadAllChannels()



    ######################
    ## Registry Handler ##
    ######################

    @inlineCallbacks
    def registrySetup(self):
        """Creates the registry directory for channel objects"""
        print("Setting up registry...")
        yield self.reg.cd(self.channelLocation,True,context=self.context)

    @inlineCallbacks
    def getAttrs(self,attr):
        prevDir = yield self.reg.cd(context=self.context)
        attrs   = []
        yield self.reg.cd(self.channelLocation,context=self.context)
        folders,files = yield self.reg.dir(context=self.context)
        for folder in folders:
            yield self.reg.cd(self.channelLocation+[folder],context=self.context)
            att = yield self.reg.get(attr,context=self.context)
            attrs.append(att)
        yield self.reg.cd(prevDir,context=self.context)
        returnValue( attrs )

    @inlineCallbacks
    def getFolderByAttr(self,attr,value):
        prevDir = yield self.reg.cd(context=self.context)
        appFolders = []
        yield self.reg.cd(self.channelLocation,context=self.context)
        folders,files=yield self.reg.dir(context=self.context)
        for folder in folders:
            yield self.reg.cd(self.channelLocation+[folder],context=self.context)
            fVal = yield self.reg.get(attr,context=self.context)
            if fVal == value:appFolders.append(folder)
        yield self.reg.cd(prevDir,context=self.context)
        returnValue( appFolders )

    @inlineCallbacks
    def delFolder(self,folder):
        prevDir = yield self.reg.cd(context=self.context)
        yield self.reg.cd(self.channelLocation+[folder],context=self.context)
        folders,files = yield self.reg.dir(context=self.context)
        for file in files:
            yield self.reg.del_(file,context=self.context)
        yield self.reg.cd(self.channelLocation,context=self.context)
        yield self.reg.rmdir(folder,context=self.context)
        try:
            yield self.reg.cd(prevDir,context=self.context)
        except:
            yield self.reg.cd(self.channelLocation,context=self.context)

    @inlineCallbacks
    def getFolderByNameID(self,ID=None,name=None):
        yield

        if (ID==None) and (name==None):
            raise ValueError("ID and name cannot both be None: at least one must be specified")

        if ID!=None:
            byID = yield self.getFolderByAttr("ID",ID)
            if len(byID) == 0:
                raise ValueError("No channels match the ID (%s) given"%ID)
            if len(byID) > 1:
                raise ValueError("Multiple channels have the same ID (%s); this should not happen."%ID)
            byID=byID[0]

        if name!=None:
            byName = yield self.getFolderByAttr("name",name)
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
        yield self.reg.cd(self.channelLocation,True,context=self.context)

        # check uniqueness of name and ID
        IDs   = yield self.getAttrs("ID")
        names = yield self.getAttrs("name")
        if ID   in IDs  : raise ValueError("ID specified is already taken.")
        if name in names: raise ValueError("Name specified is already taken.")

        # create and go to folder for new channel
        entryName = "%s (%s)"%(ID,name)
        yield self.reg.cd(self.channelLocation+[entryName],True,context=self.context)

        # write informational attributes
        yield self.reg.set("name",        name,        context=self.context) # Write the name
        yield self.reg.set("ID",          ID,          context=self.context) # Write the ID
        yield self.reg.set("label",       label,       context=self.context) # Write the label
        yield self.reg.set("description", description, context=self.context) # Write the description
        yield self.reg.set("tags",        tags,        context=self.context) # write the tags

        # write the communication entries
        yield self.reg.set("channel",      channel,      context=self.context) # Write the cahnnel
        yield self.reg.set("inputSlots",   inputSlots,   context=self.context) #
        yield self.reg.set("inputUnits",   inputUnits,   context=self.context) #
        yield self.reg.set("staticInputs", staticInputs, context=self.context) #
        yield self.reg.set("staticUnits",  staticUnits,  context=self.context) #

        # write the bounds/scale/offset entries
        yield self.reg.set("minValue", minValue, context=self.context) #
        yield self.reg.set("maxValue", maxValue, context=self.context) #
        yield self.reg.set("scale",    scale,    context=self.context) #
        yield self.reg.set("offset",   offset,   context=self.context) #

    @inlineCallbacks
    def removeChannelFromRegistry(self,ID=None,name=None):
        """Removes a channel from the registry, specified by ID and/or name"""
        folder = yield self.getFolderByNameID(ID,name)
        yield self.delFolder(folder)

    @inlineCallbacks
    def loadChannelByNameID(self,ID=None,name=None):
        channelFolder = yield self.getFolderByNameID(ID,name)
        channel       = yield self.loadChannel(channelFolder)
        returnValue( channel )

    @inlineCallbacks
    def boundInterp(self,boundList):
        newList = []
        for inst in boundList:
            low=yield inst.lower()
            if low in self.noneTypes:
                newList.append(None)
            else:
                newList.append(float(inst))
        returnValue( newList )


    @inlineCallbacks
    def loadChannel(self,channelFolder):
        """Loads a channel from the registry to a settingChannel object"""

        # go to channel folder
        yield self.reg.cd(self.channelLocation+[channelFolder],context=self.context)

        ID          = yield self.reg.get("ID"         ,context=self.context)
        name        = yield self.reg.get("name"       ,context=self.context)
        label       = yield self.reg.get("label"      ,context=self.context)
        description = yield self.reg.get("description",context=self.context)
        tags        = yield self.reg.get("tags"       ,context=self.context)

        channel      = yield self.reg.get("channel"     ,context=self.context)
        inputSlots   = yield self.reg.get("inputSlots"  ,context=self.context)
        inputUnits   = yield self.reg.get("inputUnits"  ,context=self.context)
        staticInputs = yield self.reg.get("staticInputs",context=self.context)
        staticUnits  = yield self.reg.get("staticUnits" ,context=self.context)

        minValue = yield self.reg.get("minValue",context=self.context)
        maxValue = yield self.reg.get("maxValue",context=self.context)
        scale    = yield self.reg.get("scale"   ,context=self.context)
        offset   = yield self.reg.get("offset"  ,context=self.context)

        minValue = yield self.boundInterp(minValue) # These settings are stored as strings so that they can be either numbers or None (no constraints / scaling)
        maxValue = yield self.boundInterp(maxValue) # If they are interpretable as Nonetype ("None","none","-","") they will be set to None
        scale    = yield self.boundInterp(scale)    # Otherwise they will be interpreted as a float
        offset   = yield self.boundInterp(offset)   # 


        returnValue( settingChannel(ID,name,label,description,tags,channel,inputSlots,staticInputs,inputUnits,staticUnits,minValue,maxValue,scale,offset) )

    @inlineCallbacks
    def loadAllChannels(self):
        yield self.reg.cd(self.channelLocation,context=self.context)
        folders,files=yield self.reg.dir(context=self.context)
        channels = []
        for channelFolder in folders:
            ch = yield self.loadChannel(channelFolder)
            channels.append(ch)

        returnValue( [{ch.ID:ch for ch in channels},{ch.name:ch for ch in channels}] )


    ##############
    ## Settings ##
    ##############

    @setting(1,"Add Channel",
        ID           = 's' ,
        name         = 's' ,
        label        = 's' ,
        description  = 's' ,
        tags         = '*s',
        channel      = '*s',
        inputSlots   = '*i',
        staticInputs = '*s',
        inputUnits   = '*s',
        staticUnits  = '*s',
        minValue     = '*s', # list entries must be either interpretable as float, or in ["None", "none", "-", ""] (all interpreted as None)
        maxValue     = '*s', # """
        scale        = '*s', # """
        offset       = '*s', # """

        returns      = 'b{success}')
    def addChannel(self,c,ID,name,label,description,tags,channel,inputSlots,staticInputs,inputUnits,staticUnits,minValue, maxValue, scale, offset):
        """Adds a new channel to the registry.\nDoesn't overwrite; to overwrite you must delete the old channel first."""

        # Check that all values in min,max,scale,offset are float-interpretable OR nonetype
        # They will be stored as strings and interpreted when loaded. This ensures that they will be able to be interpreted.
        for inst in minValue+maxValue+scale+offset:
            if inst.lower() in self.noneTypes:
                continue
            try:
                float(inst)
            except:
                raise ValueError("Value (%s) for minValue,maxValue,scale,offset not interpetable as either float or NoneType"%inst)

        # write the channel entry
        yield self.writeChannelToRegistry(ID,name,label,description,tags,channel,inputSlots,staticInputs,inputUnits,staticUnits,minValue,maxValue,scale,offset)

        # Now add the new channel to the channel dicts
        ch = yield self.loadChannelByNameID(ID=ID)
        self.channelsByID.update([   [ID  , ch] ])
        self.channelsByName.update([ [name, ch] ])

        returnValue(True)
        
    @setting(2,"Delete Channel",ID='s',name='s',returns='b{success}')
    def delChannel(self,c,ID,name):
        """Deletes a channel specified by either its ID, name, or both"""
        if not ID  : ID   = None # Convert empty string
        if not name: name = None # to None
        yield self.removeChannelFromRegistry(ID,name)
        returnValue(True)

    @setting(100,"List Channels",returns='**s')
    def listChannels(self,c):
        """Returns a list of channels [ [ID,name], [ID,name], ... ]"""
        keys = yield self.channelsByID.keys()
        returnValue([ [str(key),self.channelsByID[key].name] for key in keys])

    @setting(500,"send channel request",ID='s',name='s',inputs='*s',context='*i',selectDevice='b',returns="?")
    def sendChannelRequest(self,c,ID,name,inputs,context,selectDevice):
        if ID:
            ch = yield self.channelsByID[ID]
        elif name:
            ch = yield self.channelsByName[name]
        else:
            yield
            raise ValueError("At least one of (ID,name) must be specified.")

        # empty context -> None
        if len(context)==0:context=None

        nInputs=len(inputs)
        if nInputs != ch.nNonStaticInputs:raise ValueError("number of inputs does not match number of inptut slots")

        # if specified, select the device
        if selectDevice:
            if not (context is None): yield self.client[ch.channel[0]].select_device(ch.channel[1],context=context)
            else                    : yield self.client[ch.channel[0]].select_device(ch.channel[1])

        # for zero inputs: just call the setting alone < setting() >
        if ch.nTotalInputs == 0:
            if not (context is None):
                resp = yield self.client[ch.channel[0]][ch.channel[2]](context=context)
            else:
                resp = yield self.client[ch.channel[0]][ch.channel[2]]()
            returnValue( resp )

        # convert inputs and static inptus to specified types
        _statics = []
        for pos in range(ch.nStaticInputs):
            val = yield toType(ch.staticInputs[pos],ch.staticUnits[pos])
            _statics.append(val)

        _nonstat = []
        for pos in range(ch.nNonStaticInputs):
            val = yield toType(inputs[pos],ch.inputUnits[pos])
            _nonstat.append(val)

        # apply offset and scale, enforce bounds
        for pos in range(ch.nNonStaticInputs):
            if ch.scale[pos]    != None : _nonstat[pos] *= ch.scale[pos]
            if ch.offset[pos]   != None : _nonstat[pos] += ch.offset[pos]
            if ch.minValue[pos] != None :
                if _nonstat[pos] < ch.minValue[pos]:
                    raise ValueError("Value deceeds minimum value <entry number: %s>, <minimum value: %s>, <value found: %s>, <offset: %s>, <scale: %s>"%(pos,ch.minValue[pos],_nonstat[pos],ch.offset[pos],ch.scale[pos]))
            if ch.maxValue[pos] != None :
                if _nonstat[pos] > ch.maxValue[pos]:
                    raise ValueError("Value exceeds maximum value <entry number: %s>, <minimum value: %s>, <value found: %s>, <offset: %s>, <scale: %s>"%(pos,ch.minValue[pos],_nonstat[pos],ch.offset[pos],ch.scale[pos]))

        # assemble input list
        assembly = yield assembleList(ch.inputSlots,_nonstat,_statics)

        # for one input: call the setting with that value < setting(value) >
        if ch.nTotalInputs == 1:
            if not (context is None):
                resp = yield self.client[ch.channel[0]][ch.channel[2]](assembly[0],context=context)
            else:
                resp = yield self.client[ch.channel[0]][ch.channel[2]](assembly[0])
            returnValue( resp )

        # for multiple inputs, call the setting with the list of inputs < setting([inputs]) >
        else:
            if not (context is None):
                resp = yield self.client[ch.channel[0]][ch.channel[2]](assembly,context=context)
            else:
                resp = yield self.client[ch.channel[0]][ch.channel[2]](assembly)
            returnValue( resp )





__server__ = VirtualDeviceServer()
if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
