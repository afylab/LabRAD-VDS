# LabRAD-VDS
Virtual Device Server for LabRAD. Handles dedicated output channels.

## Status
Not yet functioning

### progress
- [x] Server runs
- [x] registry structure present
- [x] functions to add/remove channels to/from registry
- [x] list_channels functionality
- [x] Send channel request function
- [ ] Listeners/signals for valueChanged signals
- [ ] Functions for reading / modifying channel details
- [ ] Determine which channels are active
- [ ] Signals for channels opening/closing?

VDS2 is the new version being developed; it has the new registry structure where a channel has a get and/or set command.

### progress of VDS2
- [x] registry structure
- [x] create/delete registry objects
- [x] read & load channels from registry
- [ ] send get and set commands
- [ ] detect which channels are active