from flask import Flask
from flask_restplus import Resource, Api
from time import sleep
import pandas as pd

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

import subprocess
import time

portx=3105

l_loop = "1.1.1.1"
r_loop = "2.2.2.2"

#sudo_password = "!PDPstr0ngpassword1"
sudo_password = "Tecip2024"

interfaces = {
   1: "Ethernet0",
   2: "Ethernet8",
   3: "Ethernet16",
   4: "Ethernet24",
   5: "Ethernet32",
   6: "Ethernet40",
   7: "Ethernet48",
   8: "Ethernet56",
   9: "Ethernet64",
   10: "Ethernet72",
   11: "Ethernet80",
   12: "Ethernet88",
   13: "Ethernet96",
   14: "Ethernet104",
   15: "Ethernet112",
   16: "Ethernet120",
   17: "Ethernet128",
   18: "Ethernet136",
   19: "Ethernet144",
   20: "Ethernet152",
   21: "Ethernet160",
   22: "Ethernet168",
   23: "Ethernet176",
   24: "Ethernet184",
   25: "Ethernet192",
   26: "Ethernet200",
   27: "Ethernet208",
   28: "Ethernet216",
   29: "Ethernet224",
   30: "Ethernet232",
   31: "Ethernet240",
   32: "Ethernet248",
   33: "Ethernet256",
   34: "Ethernet257",
}

speeds = {
   "SPEED_10MB": 10,
   "SPEED_100MB": 100,
   "SPEED_1GB": 1000,
   "SPEED_250MB": 250,
   "SPEED_5GB": 5000,
   "SPEED_10GB": 10000,
   "SPEED_25GB": 25000,
   "SPEED_40GB": 40000,
   "SPEED_50GB": 50000,
   "SPEED_100GB": 100000,
   "SPEED_200GB": 200000,
   "SPEED_400GB": 400000,
   "SPEED_600GB": 600000,
   "SPEED_800GB": 800000
}

def interface_output_parser(text):
    temp = {}
    lines = text.split('\n')
    for i in range(2, len(lines)-1):
        # 0      1      2     3          4      5     6     7     8      9    10    11
        #[ifx, lanes, speed, mtu, oper, fec, aliasx, vlan, oper, admin, type, asym, oper2] = lines[i].split()
        a = lines[i].split()
        print (i, a)
        temp[a[0]] = {}
        temp[a[0]]["interface"] = a[0]
        temp[a[0]]["speed"] = a[2]
        temp[a[0]]["oper"] = a[7]
        temp[a[0]]["alias"] = a[5]
        temp[a[0]]["lanes"] = a[1]
        temp[a[0]]["type"] = a[9]
    return temp


def frequency_output_parser(text):
    temp = {}
    lines = text.split('\n')
    for i in range(2, len(lines)-1):
        # 0      1      2     3          4      5     6     7     8      9    10    11
        #[ifx, lanes, speed, mtu, oper, fec, aliasx, vlan, oper, admin, type, asym, oper2] = lines[i].split()
        a = lines[i].split()
        print (i, a)
        temp[a[0]] = {}
        temp[a[0]]["interface"] = a[0]
        temp[a[0]]["frequency"] = a[1]
        temp[a[0]]["grid"] = a[2]
    return temp


def decimal_to_hex(number):
    multiplied = int(number * 100)
    # If the number is negative, convert to two's complement
    if multiplied < 0:
        # For two's complement, find the positive equivalent (absolute value)
        abs_value = abs(multiplied)
        # Assume 16-bit two's complement, calculate the two's complement by subtracting from 2^16
        twos_complement_value = (1 << 16) - abs_value
        # Convert to hex
        hex_result = hex(twos_complement_value)
    else:
        # If it's positive, just convert to hex normally
        hex_result = hex(multiplied)
    
    a1 = hex_result[2:4]
    a2 = hex_result[-2:]
    
    return hex_result, a1, a2

def port_mapping(port):
    prefix, val = port.split('net')
    port_num = int(val)
    port_id_val = int(port_num/8) + 1 
    #port_id_num = int(port_id%8)
    #if port_id_num != 0:
    #  print(f"{port_id_val}/{port_id_num}")
    #else:
    #  print(f"{port_id_val}")
    return port_id_val

def filter_sfp_info(data):
    # separate the data by interface sections
    interface_sections = data.split("\n\n")
    # dictionary to store results
    result = {}
    for section in interface_sections:
        lines = section.strip().splitlines()
        if lines:
            interface_name = lines[0].split()[0]  # Assuming the first word in the section is the interface name
            # Process each line within the section
            processed_lines = [[item.strip() for item in line.split(":", 1)] for line in lines if ":" in line]
            # Create a DataFrame from processed lines
            df = pd.DataFrame(processed_lines, columns=["Key", "Value"])
            # Filter the DataFrame for specific keywords
            filtered_df = df[df['Key'].str.lower().str.startswith(('supported', 'vendor', 'media', 'identifier'))]
            # Convert filtered DataFrame to a plain text list
            filtered_text_list = [f"{row['Key']}: {row['Value']}" for _, row in filtered_df.iterrows()]
            # interface name as the key
            result[interface_name] = filtered_text_list
    return result


def is_reachable(ip):
    command = ["ping", "-c", "1", ip, "-W", "1"]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
        return False

# Flask and Flask-RestPlus configuration
app = Flask(__name__)
api = Api(app, version='1.0', title='Sonic API',
          #description='Rest API to setup Interface in Sonic devices. \nAuthor: Andrea Sgambelluri and Davide Scano')
          description='Rest API to setup Interface in Sonic IPoWDM devices. \nAuthor: Andrea Sgambelluri')
sonic = api.namespace('Sonic', description='Sonic APIs')

#This REST implemnets all the commands used in https://github.com/Dscano/Testbed-OFC22/blob/main/Configs/Cnit54/config.md#config-port-192
#STEP1
@sonic.route('/Interface/<string:ip>/<int:mask>/<string:interface>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _config_Interface_IP(Resource):
    @sonic.doc(description="Interface IP configuration")
    @staticmethod
    def put(ip, mask, interface):
            # str(interfaces[interface])
            global sudo_password
            #sudo_password = 'YourPaSsWoRd'
            command = 'config interface ip add ' + str(interface) + ' ' + str(ip) + '/'+ str(mask)
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            return "OK", 200

    @sonic.doc(description="delete Interface IP configuration")
    @staticmethod
    def delete(ip, mask, interface):            
            global sudo_password
            command = 'config interface ip remove ' + str(interface) + ' ' + str(ip) + '/'+ str(mask)
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            return "OK", 200


#STEP4
@sonic.route('/reach/<string:ip_address>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _reach(Resource):
    @sonic.doc(description="l2vpn vni configuration")
    @staticmethod
    def put(ip_address):
      print("aaa")
      while 1:
        # Example usage
        #ip_address = "192.168.252.2"
        if is_reachable(ip_address):
          print(f"{ip_address} is reachable.")
          break
        else:
          print(f"{ip_address} is not reachable.")
      return "OK", 200



#STEP4
@sonic.route('/vni/<int:vlan_id>/<int:vni>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _config_vni(Resource):
    @sonic.doc(description="l2vpn vni configuration")
    @staticmethod
    def put(vlan_id, vni):
        global sudo_password
        #command = f'config vlan add {vlan_id}'
        #p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
        #    , universal_newlines=True)
        #p.communicate(sudo_password + '\n')[1]
        command = f'config vxlan map add vxlan10 {vlan_id} {vni}'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        print('Done!')
        return "OK", 200

    @sonic.doc(description="delete vni")
    @staticmethod
    def delete(vlan_id, vni):            
        global sudo_password
        command = f'config vxlan map del vxlan10 {vlan_id} {vni}'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        print('Done!')
        return "OK", 200

@sonic.route('/route/<string:net>/<string:mask>/<string:gw>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _config_route(Resource):
    @sonic.doc(description="Interface IP configuration")
    @staticmethod
    def put(net, gw, mask):
        global sudo_password
        if "32" in mask:
          command = f'route add {net}/{mask} gw {gw}'
          p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
          p.communicate(sudo_password + '\n')[1]
        else:
          command = f'route add -net {net}/{mask} gw {gw}'
          p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
          p.communicate(sudo_password + '\n')[1]
        print('Done!')
        return "OK", 200

    @sonic.doc(description="delete Interface IP configuration")
    @staticmethod
    def delete(net, gw, mask):            
        global sudo_password
        if "32" in mask:
          command = f'route del {net}/{mask} gw {gw}'
          p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
          p.communicate(sudo_password + '\n')[1]
        else:
          command = f'route del -net {net}/{mask} gw {gw}'
          p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
          p.communicate(sudo_password + '\n')[1]
        print('Done!')
        return "OK", 200


@sonic.route('/InterfaceConfig/<string:interface>/<string:speed>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _config_PORT(Resource):
    @sonic.doc(description="Interface UP configuration")
    @staticmethod
    def put(interface, speed):
            global sudo_password
            command = 'portconfig -p '+ str(interface) + ' -s ' + str(speeds[speed])
            #subprocess.run(['portconfig', '-p' ,command])
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            return "OK", 200

@sonic.route('/TransceiverFreqConfig/<string:interface>/<string:freq>/<string:grid>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _Transceiver_config(Resource):
    @sonic.doc(description=" Transceiver frequency configuration")
    @staticmethod
    def put(interface, freq, grid):
            global sudo_password
            #sudo_password = 'YourPaSsWoRd'
            if len(freq) > 6:
                print(freq)
                ffreq = freq[:4] + "00"
                freq = ffreq
                print(freq)
            if "channel-" in interface:
                temp = interface.replace("channel-", "Ethernet")
                interface = temp
            command = 'portconfig -p '+ str(interface) + ' -F ' + str(freq) + ' -G ' + str(grid)
            print(command)
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            return "OK", 200

@sonic.route('/TransceiverConfigAll/<string:interface>/<string:freq>/<string:grid>/<string:power>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _Transceiver_config(Resource):
    @sonic.doc(description=" Transceiver frequency configuration")
    @staticmethod
    def put(interface, freq, grid, power):
            global sudo_password
            if len(freq) > 6:
                print(freq)
                ffreq = freq[:4] + "00"
                print(ffreq)
                freq = ffreq
                print(freq)
            #sudo_password = 'YourPaSsWoRd'
            command = 'portconfig -p '+ str(interface) + ' -F ' + str(freq) + ' -G ' + str(grid) + ' -P ' + str(power)
            print(command)
            #subprocess.run(['portconfig', '-p' ,command])
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            return "OK", 200


@sonic.route('/FastPowerConfig/<string:interface>/<string:power>')
@sonic.response(200, 'Success')
class _Fast_Transceiver_config(Resource):
    @sonic.doc(description=" Transceiver power configuration")
    @staticmethod
    def put(interface, power):
            global sudo_password
            #value = round(float(power),2)
            #hex_result, a1, a2 = decimal_to_hex(value)
            #prefix, val = port.split('net')
            #port_num = int(val)
            #port_id_val = int(port_num/8) + 1 
            #port_id_num = int(port_id%8)
            #if port_id_num != 0:
            #  print(f"{port_id_val}/{port_id_num}")
            #else:
            #  print(f"{port_id_val}")
            if 'net' not in interface:
                return "Please specify a valid Ethernet value", 404
            port_id_val = port_mapping(interface)
            print(port_id_val)
            command = f'bash /home/admin/REST/txpower.sh {port_id_val} {power}'
            print(command)
            #subprocess.run([command])
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            '''
            #sudo_password = 'YourPaSsWoRd'
            print(command)
            #subprocess.run(['portconfig', '-p' ,command])
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            '''
            return (port_id_val), 200



@sonic.route('/TransceiverPowerConfig/<string:interface>/<string:power>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _Transceiver_config(Resource):
    @sonic.doc(description=" Transceiver power configuration")
    @staticmethod
    def put(interface, power):
            global sudo_password
            if 'net' not in interface:
                return "Please specify a valid Ethernet value", 404

            command = 'portconfig -p '+ str(interface) + ' -P ' + str(power)
            print(command)
            #subprocess.run(['portconfig', '-p' ,command])
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            return "OK", 200

@sonic.route('/TransceiverConfig/<string:interface>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _Transceiver_get(Resource):
    @sonic.doc(description=" Transceiver get measurements")
    @staticmethod
    def get(interface):
        if 'net' not in interface:
           return "Please specify a valid Ethernet value", 404
        port = port_mapping(interface)
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
        platform_sfputil = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper()
        sfp = platform_chassis.get_sfp(port)
        apix = sfp.get_xcvr_api()
        vals = CmisApi.get_vdm(apix)
        #freq = CCmisApi.get_laser_config_freq(api)
        #grid = CCmisApi.get_freq_grid(api)
        #power = CCmisApi.get_tx_power(api)
        ber = round(float(vals['Pre-FEC BER Current Value Media Input'][1][0]),6)
        osnr = round(float(vals['OSNR [dB]'][1][0]), 2)
        esnr = round(float(vals['eSNR [dB]'][1][0]),2)
        #return "RX={}\nBER={}\nOSNR={}\neSNR={}".format(rx, ber, osnr, esnr), 200
        return "BER={} \
                OSNR={} \
                eSNR={}".format(ber, osnr, esnr), 200


@sonic.route('/InterfaceStatus/<string:interface>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _config_Interface_UP(Resource):
    @sonic.doc(description="Activate Interface")
    @staticmethod
    def put(interface):
            global sudo_password
            #sudo_password = 'YourPaSsWoRd'
            if 'net' not in interface:
                return "Please specify a valid Ethernet value", 404

            command = 'config interface startup ' + str(interface)
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            return "OK", 200

    @sonic.doc(description="Disable Interface")
    @staticmethod
    def delete(interface):
            global sudo_password
            if 'net' not in interface:
                return "Please specify a valid Ethernet value", 404
            #sudo_password = 'YourPaSsWoRd'
            command = 'config interface shutdown ' + str(interface)
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
                , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            print('Done!')
            return "OK", 200      
    
#BGP
#Implements https://github.com/Dscano/Testbed-OFC22/blob/main/Configs/Cnit54/config.md#bgp-configuration
@sonic.route('/bgp/<int:aut>/<int:remo_aut>/<string:ip>/<string:interface>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class confBgpRoute(Resource):
    @sonic.doc(description="Configure BGP route")
    @staticmethod
    def put(aut,remo_aut,ip,interface):
        if isinstance(aut,int):
             # str(interfaces[port])
            com1 = 'conf t \n router bgp ' + str(aut) + '\n neighbor '+ ip + ' remote-as ' + str(remo_aut)  \
            + ' \n neighbor '+ ip + ' interface ' + str(interface) + '\n address-family ipv4 unicast' \
            + '\n neighbor '+ ip + ' activate'
            subprocess.run(['vtysh', '-c', com1])
            process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
            com2 = 'conf t \n router bgp ' + str(aut) + '\n address-family ipv4 unicast' \
            + ' \n redistribute static  \n redistribute connected'
            subprocess.run(['vtysh', '-c', com2])
            process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
            com3 = 'conf t \n access-list ALLOW_ALL permit any \n route-map PERMIT_ALL permit 1 \n match ip address ALLOW_ALL'
            subprocess.run(['vtysh', '-c', com3])
            process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
            if "saved" in str(process.stdout):
                return 'Success', 200
            else:
                return 'Success', 404

#Implements https://github.com/Dscano/Testbed-OFC22/blob/main/Configs/Cnit54/config.md#unconfigure-base-configuration
@sonic.route('/bgp/<int:aut>/')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class removeBgpRoute(Resource):
    @sonic.doc(description="Remove BGP route")
    @staticmethod
    def delete(aut):
        if isinstance(aut,int):
            com1 = 'conf t \n no router bgp ' + str(aut) 
            subprocess.run(['vtysh', '-c', com1])
            process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
            com2 = 'conf t \n no route-map FROM_BGP_PEER_V6  \n no route-map FROM_BGP_PEER_V4 \n no route-map TO_BGP_PEER_V4' \
            '\n no route-map TO_BGP_PEER_V6 \n no route-map ALLOW_LIST_DEPLOYMENT_ID_0_V4 \n no route-map ALLOW_LIST_DEPLOYMENT_ID_0_V6'
            process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
            subprocess.run(['vtysh', '-c', com2])
            process2 = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
            if ("saved" in str(process.stdout)) & ("saved" in str(process2.stdout)):
                return 'Success', 200
            else:
                return 'Success', 404

@sonic.route('/bgp/neighbor/<int:aut>/<int:remo_aut>/<string:ip>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class removeBgpNeighbor(Resource):
    @sonic.doc(description="Remove BGP neighbor")
    @staticmethod
    def delete(aut,remo_aut,ip):
        if isinstance(aut,int):
            # str(interfaces[port])
            com1 = 'conf t \n  router bgp ' + str(aut) + '\n no neighbor '+ ip + ' remote-as ' + str(remo_aut)
            subprocess.run(['vtysh', '-c', com1])
            process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
            if "saved" in str(process.stdout):
                return 'Success', 200
            else:
                return 'Success', 404






@sonic.route('/l2vpn/<int:aut>/<int:remo_aut>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class removeBgpNeighbor(Resource):
    @sonic.doc(description="xvxlan and l2vpn BGP neighbor")
    @staticmethod
    def put(aut,remo_aut):
        global sudo_password
        command = f'config vxlan add vxlan10 {l_loop}'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        #time.sleep(3)
        command = f'config vxlan evpn_nvo add nvo vxlan10'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        #time.sleep(3)
        #com = 'conf t \n router bgp ' + str(aut) + '\n bgp router-id ' + l_loop + ' \n bgp graceful-restart \n no bgp default ipv4-unicast \n' \
        #      ' neighbor ' + r_loop + ' remote-as ' + str(remo_aut) + '\n neighbor ' + r_loop + ' update-source ' + l_loop + '\n'  \
        #      ' address-family l2vpn evpn \n neighbor ' + r_loop + ' activate \n advertise-all-vni \n exit-address-family \n ! \n address-family ipv4 unicast \n' \
        #      ' network ' + l_loop +'/32 \n neighbor ' + r_loop + ' activate \n'
        com1 = 'conf t \n router bgp ' + str(aut) + '\n bgp router-id ' + l_loop + ' \n bgp graceful-restart \n no bgp default ipv4-unicast \n' \
              ' neighbor ' + r_loop + ' remote-as ' + str(remo_aut) + '\n neighbor ' + r_loop + ' update-source Loopback0'
        # + l_loop 
        print(com1)
        subprocess.run(['vtysh', '-c', com1])       
        process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
        print(process.stdout)
        com2 = 'conf t \n router bgp ' + str(aut) + '\n address-family l2vpn evpn \n neighbor ' + r_loop + ' activate \n advertise-all-vni \n exit-address-family \n ! \n address-family ipv4 unicast \n' \
              ' network ' + l_loop +'/32 \n neighbor ' + r_loop + ' activate \n exit-address-family \n end \n exit'
        print(com2)
        subprocess.run(['vtysh', '-c', com2])       
        process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)
        print(process.stdout)
        
        if "saved" in str(process.stdout):
            return 'Success', 200
        else:
            return 'Success', 404

    @sonic.doc(description="delete xvxlan and l2vpn BGP neighbor")
    @staticmethod
    def delete(aut,remo_aut):
        command = f'sudo config vxlan evpn_nvo del nvo'
        p = subprocess.run(command.split(' '), capture_output=True, text=True)
        #time.sleep(3)
        command = f'sudo config vxlan del vxlan10'
        p = subprocess.run(command.split(' '), capture_output=True, text=True)
        #time.sleep(3)
        com = 'conf t \n no route-map RM_SET_SRC \n no ip protocol bgp route-map RM_SET_SRC \n no router bgp ' + str(aut) + '\n'
        subprocess.run(['vtysh', '-c', com])
        process = subprocess.run(['vtysh', '-c', 'write'], stdout=subprocess.PIPE)

        if "saved" in str(process.stdout):
            return 'Success', 200
        else:
            return 'Success', 404



#@sonic.route('/GetInterfaces/<string:interface>/<int:simple>')
@sonic.route('/GetInterfaces/<string:interface>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _get_Interfaces(Resource):
    @sonic.doc(description="Interface UP configuration")
    @staticmethod
    def get(interface):
            simple = 1
            command = 'show interfaces status'
            if interface != "all":
              command = 'show interfaces status ' + interface
            #subprocess.run(['portconfig', '-p' ,command])
            p = subprocess.run(command.split(' '), capture_output=True, text=True)
            #p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            #    , universal_newlines=True, capture)
            #result = p.communicate(sudo_password + '\n')[0]
            val = p.stdout
            #print(result)
            if simple:
                result = interface_output_parser(val)
            else:
                result = val
            return result, 200



#@sonic.route('/GetInterfaces/<string:interface>/<int:simple>')
@sonic.route('/GetIPAddresses/<string:interface>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _get_IpAddresses(Resource):
    @sonic.doc(description="Interface UP configuration")
    @staticmethod
    def get(interface):
            simple = 1
            command = 'show ip interfaces'
            if interface != "all":
              command = 'show ip interfaces ' + interface
            #subprocess.run(['portconfig', '-p' ,command])
            p = subprocess.run(command.split(' '), capture_output=True, text=True)
            #p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            #    , universal_newlines=True, capture)
            #result = p.communicate(sudo_password + '\n')[0]
            val = p.stdout
            #print(result)
            #if simple:
            #    result = output_parser(val)
            #else:
            #    result = val
            #return result, 200
            print(val)
            return val, 200


@sonic.route('/vlan_member/<int:vlan_id>/<string:interface>/<int:typex>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _vlans(Resource):
    @sonic.doc(description="vlan configuration")
    @staticmethod
    def put(vlan_id, interface, typex):
        global sudo_password
        #command = f'sudo config vlan add {vlan_id}'
        #p = subprocess.run(command.split(' '), capture_output=True, text=True)
        #val = p.stdout            
        if typex == 1:
            command = f'config interface shutdown {interface}'
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            time.sleep(1)
            command = f'config vlan member add -u {vlan_id} {interface}'
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            time.sleep(1)
            command = f'config interface startup {interface}'
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
        else:
            command = f'config interface shutdown {interface}'
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            time.sleep(1)
            command = f'config vlan member add {vlan_id} {interface}'
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
            time.sleep(1)
            command = f'config interface startup {interface}'
            p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
            p.communicate(sudo_password + '\n')[1]
        return "ok", 200

    @staticmethod
    def delete(vlan_id, interface, typex):
        command = f'config interface shutdown {interface}'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        time.sleep(1)
        command = f'config vlan member del {vlan_id} {interface}'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        time.sleep(1)
        command = f'config interface startup {interface}'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        return "ok", 200

@sonic.route('/vlan/<int:vlan_id>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _vlans(Resource):
    @sonic.doc(description="vlan configuration")
    @staticmethod
    def put(vlan_id):
        global sudo_password
        command = f'config vlan add {vlan_id}'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        return "ok", 200

    @staticmethod
    def delete(vlan_id):
        command = f'config vlan del {vlan_id}'
        p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            , universal_newlines=True)
        p.communicate(sudo_password + '\n')[1]
        return "ok", 200


#@sonic.route('/GetInterfaces/<string:interface>/<int:simple>')
@sonic.route('/GetFrequencies/<string:interface>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _get_Frequencies(Resource):
    @sonic.doc(description="Interface UP configuration")
    @staticmethod
    def get(interface):
            simple = 1
            command = 'show interfaces transceiver frequency'
            if interface != "all":
              command = 'show interfaces transceiver frequency ' + interface
            #subprocess.run(['portconfig', '-p' ,command])
            p = subprocess.run(command.split(), capture_output=True, text=True)
            #p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            #    , universal_newlines=True, capture)
            #result = p.communicate(sudo_password + '\n')[0]
            val = p.stdout
            #print(result)
            if simple:
                result = frequency_output_parser(val)
            else:
                result = val
            #print(val)
            #return val, 200
            return result, 200


#@sonic.route('/GetInterfaces/<string:interface>/<int:simple>')
@sonic.route('/GetSfpInfo/<string:interface>')
@sonic.response(200, 'Success')
@sonic.response(404, 'Error, not found')
class _get_PortInfo(Resource):
    @sonic.doc(description="SPF Information")
    @staticmethod
    def get(interface):
            simple = 1
            command = 'show interfaces transceiver eeprom' if interface == "all" else f'show interfaces transceiver eeprom {interface}'
            p = subprocess.run(command.split(), capture_output=True, text=True)
            # Check if the command succeeded
            if p.returncode == 0:
                data = p.stdout
                 # Call the modified filter function
                result = filter_sfp_info(data)
                return {"result": result}, 200
            else:
                 # Return an error if the command failed
                 print(f"Error: {p.stderr}")
                 return {"error": f"Error executing command: {p.stderr}"}, 404

if __name__ == '__main__':
    #additional functions
    app.run(host='0.0.0.0', port=portx)

