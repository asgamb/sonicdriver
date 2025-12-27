from sonic_platform_base.sonic_xcvr.codes.public.cmis import CmisCodes
from sonic_platform_base.sonic_xcvr.api.public.cmis import CmisApi
from sonic_platform_base.sonic_xcvr.api.public.c_cmis import CCmisApi
from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis import CmisMemMap
from sonic_platform_base.sonic_xcvr.api.public.cmisVDM import CmisVdmApi

from sonic_platform_base.sonic_xcvr.codes.public.sff8436 import Sff8436Codes
from sonic_platform_base.sonic_xcvr.api.public.sff8436 import Sff8436Api
from sonic_platform_base.sonic_xcvr.mem_maps.public.sff8436 import Sff8436MemMap

from sonic_platform_base.sonic_xcvr.codes.public.sff8636 import Sff8636Codes
from sonic_platform_base.sonic_xcvr.api.public.sff8636 import Sff8636Api
from sonic_platform_base.sonic_xcvr.mem_maps.public.sff8636 import Sff8636MemMap

from sonic_platform_base.sonic_xcvr.codes.public.sff8472 import Sff8472Codes
from sonic_platform_base.sonic_xcvr.api.public.sff8472 import Sff8472Api
from sonic_platform_base.sonic_xcvr.mem_maps.public.sff8472 import Sff8472MemMap

from sonic_platform_base.sonic_xcvr.xcvr_eeprom import XcvrEeprom
from sonic_platform_base.sonic_xcvr.api.xcvr_api import XcvrApi

import sonic_platform.platform
import sonic_platform_base.sonic_sfp.sfputilhelper
import time
import redis
from flask import Flask
from flask_restplus import Resource, Api
from threading import Thread
from threading import Event
from TelemetryAdaptor import TelemetryAdaptor
import json

TRANSCEIVER_DOM_SENSOR_TABLE = 'TRANSCEIVER_DOM_SENSOR'

interface = "Ethernet208"
pport= 27
platform_chassis = sonic_platform.platform.Platform().get_chassis()
sfp = platform_chassis.get_sfp(int(pport))
apix = sfp.get_xcvr_api()
r = redis.Redis(host='localhost', port=6379, db=6)
d1 = r.hgetall(TRANSCEIVER_DOM_SENSOR_TABLE + '|' + interface)
d = {k.decode('utf8'): v.decode('utf8') for k, v in d1.items()}
print(d)
vals = CmisApi.get_vdm(apix)
print(vals)
