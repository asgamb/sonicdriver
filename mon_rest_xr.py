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
import subprocess
from confluent_kafka import Producer
from measurements import MyMeasurement, MeasurementEncoder
TRANSCEIVER_DOM_SENSOR_TABLE = 'TRANSCEIVER_DOM_SENSOR'

interface = "Ethernet48"
pport= 7


#portx = 3106
portx = 3116


# Flask and Flask-RestPlus configuration
app = Flask(__name__)
api = Api(app, version='1.0', title='Sonic API',
          description='Rest API to get data from pluggables. \nAuthor: Andrea Sgambelluri')
monitoring = api.namespace('Monitoring', description='Sonic APIs')
sudo_password = "Tecip2024"
events = {}
threads = {}
jobs = {}
thread_id = 1
config_file = "config.json"
config = None

kafkaIP = "10.30.2.119"
kafkaPort = 9191

topic = "OpticalNetworkTFS"
# topic = "INtopic"
# topic = "Test"
conf = {'bootstrap.servers': kafkaIP + ":" + str(kafkaPort)}

p = Producer(**conf)



def responder(interface):
   resp = {}
   pport = port_mapping(interface)
   platform_chassis = sonic_platform.platform.Platform().get_chassis()
   platform_sfputil = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper()
   sfp = platform_chassis.get_sfp(int(pport))
   apix = sfp.get_xcvr_api()
   r = redis.Redis(host='localhost', port=6379, db=6)
   d1 = r.hgetall(TRANSCEIVER_DOM_SENSOR_TABLE + '|' + interface)
   d = {k.decode('utf8'): v.decode('utf8') for k, v in d1.items()}
   tx = round(float(d['tx_curr_power']), 2)
   rx_tot = round(float(d['rx_tot_power']), 2)
   rx_sig = round(float(d['rx_sig_power']), 2)
   vals = CmisApi.get_vdm(apix)
   ber = round(float(vals['Pre-FEC BER Current Value Media Input'][1][0]),6)
   osnr = round(float(vals['OSNR [dB]'][1][0]), 2)
   esnr = round(float(vals['eSNR [dB]'][1][0]),2)
   resp['tx'] = tx
   resp['rx_tot'] = rx_tot
   resp['rx_sig'] = rx_sig
   resp['ber'] = ber
   resp['osnr'] = osnr
   resp['esnr'] = esnr
   return resp


def delivery_callback(err, msg):
    if err:
        print('%% Message failed delivery: %s\n' % err)
    else:
        print('%% Message delivered to %s [%d] @ %d\n' %
                         (msg.topic(), msg.partition(), msg.offset()))

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

def port_mapping_xr(val):
    port_num = int(val)
    port_id_val = int(port_num/8) + 1
    return port_id_val

def telemetry_task(event, thread_idx, interface, mode):
    global config
    telemetry_adaptor = TelemetryAdaptor(config["redis"])  # configuration for the telemetry adaptor
    sleep_time = config["sleep_time"]  # telemetry period
    header = config["header"]  # header to attach to the telemetry sample
    header["tags"]["interface"] = "{}".format(interface)
    print('Telemetry job {} starting...'.format(thread_idx))

    while True:
        data_body = {}
        pport = port_mapping(interface)

        platform_chassis = sonic_platform.platform.Platform().get_chassis()
        sfp = platform_chassis.get_sfp(int(pport))
        apix = sfp.get_xcvr_api()
        r = redis.Redis(host='localhost', port=6379, db=6)
        d1 = r.hgetall(TRANSCEIVER_DOM_SENSOR_TABLE + '|' + interface)
        d = {k.decode('utf8'): v.decode('utf8') for k, v in d1.items()}
        tx = round(float(d['tx_curr_power']), 2)
        rx_tot = round(float(d['rx_tot_power']), 2)
        rx_sig = round(float(d['rx_sig_power']), 2)
        vals = CmisApi.get_vdm(apix)
        ber = round(float(vals['Pre-FEC BER Current Value Media Input'][1][0]), 6)
        osnr = round(float(vals['OSNR [dB]'][1][0]), 2)
        esnr = round(float(vals['eSNR [dB]'][1][0]),2)

        data_body["tx-power"] = tx
        data_body["rx-power"] = rx_tot
        data_body["sig-rx-power"] = rx_sig
        data_body["BER"] = ber
        data_body["osnr"] = osnr
        data_body["esnr"] = esnr
        msg = "Telemetry thread {} --> {}".format(thread_idx, data_body)
        print(msg)
        if mode > 0:
            try:
                data_json = {"header": header, "body": data_body}
                data = json.dumps(data_json)
                telemetry_adaptor.write_to_redis(data)
            except:
                print("Error connecting to Redis, server is unreachable!")
            # check for stop

        if event.is_set():
            break
        time.sleep(sleep_time)
    print('Telemetry thread {} closing down'.format(thread_idx))


def kafka_task(event, thread_idx, interface):
    print('Telemetry job {} starting...'.format(thread_idx))

    while True:
        fields = responder(interface)
        measurement = MyMeasurement()
        measurement.setName('optical_measurement')
        measurement.setTag('device', 'edgecore1')
        measurement.setTag('interface', interface)
        measurement.setTimestamp(int(time.time() * 1000))

        for key, value in fields.items():
            measurement.addField(key, value)

        print(measurement)

        p.produce(topic, value=json.dumps(measurement, cls=MeasurementEncoder).encode(), callback=delivery_callback)
        p.flush()
        p.poll(1)

        time.sleep(2)
        if event.is_set():
            break
        time.sleep(2)
    print('Telemetry thread {} closing down'.format(thread_idx))


@monitoring.route('/get-data/<string:interface>/<int:mode>')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _getData(Resource):
    @staticmethod
    def get(interface, mode):
       lines = []
       pport = port_mapping(interface)
       platform_chassis = sonic_platform.platform.Platform().get_chassis()
       platform_sfputil = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper()
       sfp = platform_chassis.get_sfp(int(pport))
       apix = sfp.get_xcvr_api()
       r = redis.Redis(host='localhost', port=6379, db=6)
       for i in range (0, mode):
           d1 = r.hgetall(TRANSCEIVER_DOM_SENSOR_TABLE + '|' + interface)
           d = {k.decode('utf8'): v.decode('utf8') for k, v in d1.items()}
           #print(d)
           tx = round(float(d['tx_curr_power']), 2)
           rx_tot = round(float(d['rx_tot_power']), 2)
           rx_sig = round(float(d['rx_sig_power']), 2)
           vals = CmisApi.get_vdm(apix)
           ber = round(float(vals['Pre-FEC BER Current Value Media Input'][1][0]),6)
           osnr = round(float(vals['OSNR [dB]'][1][0]), 2)
           esnr = round(float(vals['eSNR [dB]'][1][0]),2)
           line = "{},{},{},{},{},{}".format(tx, rx_tot, rx_sig, ber, osnr, esnr)
           lines.append(line)
           print(line)
       return lines, 200


@monitoring.route('/FastPowerGet/<string:interface>')
@monitoring.response(200, 'Success')
class _Fast_Transceiver_config(Resource):
    @monitoring.doc(description=" Transceiver power monitoring")
    @staticmethod
    def get(interface):
            global sudo_password
            if 'net' not in interface:
                return "Please specify a valid Ethernet value", 404
            port_id_val = port_mapping(interface)
            print(port_id_val)
            command = f'bash /home/admin/REST/rxpower.sh {port_id_val}'
            print(command)
            #p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            #    , universal_newlines=True)
            #print(p.stdout)
            p = subprocess.run(['sudo', '-S'] + command.split(' '), capture_output=True, text=True)
            #p = subprocess.Popen(['sudo', '-S'] + command.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE
            #    , universal_newlines=True, capture)
            #result = p.communicate(sudo_password + '\n')[0]
            val = p.stdout
            val_f = round(float(val), 2)

            #p.communicate(sudo_password + '\n')[1]
            
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
            return val_f, 200


@monitoring.route('/XRConfiguredTxPowerGet/<string:interface>')
@monitoring.response(200, 'Success')
class _XR_configured_TX_power(Resource):
    @monitoring.doc(description=" XR configured TX power monitoring")
    @staticmethod
    def get(interface):
            global sudo_password
            if 'channel' in interface:
                [p, eth_num] = interface.split('-')
                interface = f"Ethernet{eth_num}"
                port_id = port_mapping_xr(eth_num)

            elif 'net' in interface:
                [p, eth_num] = interface.split('net')
                #print(p, eth_num)
                port_id = port_mapping_xr(eth_num)
                #print(port_id)
            else:
                return "Please specify a valid channel or Ethernet value", 404


            configured_tx_cmd = f"bash /home/admin/xr_control/xr_config_monitoring.sh -a {port_id}"
            print(f"Running command: {configured_tx_cmd}")


            p = subprocess.run(['sudo', '-S'] + configured_tx_cmd.split(), capture_output=True, text=True)
            
            tx_val = p.stdout
            tx_val_f = round(float(tx_val), 2)
            
            print('Done!')
            return tx_val_f, 200


@monitoring.route('/XRCurrentTxPowerGet/<string:interface>')
@monitoring.response(200, 'Success')
class _XR_current_TX_power(Resource):
    @monitoring.doc(description=" XR current TX power monitoring")
    @staticmethod
    def get(interface):
            global sudo_password
            if 'channel' in interface:
                [p, eth_num] = interface.split('-')
                interface = f"Ethernet{eth_num}"
                port_id = port_mapping_xr(eth_num)

            elif 'net' in interface:
                [p, eth_num] = interface.split('net')
                #print(p, eth_num)
                port_id = port_mapping_xr(eth_num)
                #print(port_id)
            else:
                return "Please specify a valid channel or Ethernet value", 404


            current_tx_cmd = f"bash /home/admin/xr_control/xr_config_monitoring.sh -b {port_id}"
            print(f"Running command: {current_tx_cmd}")


            p = subprocess.run(['sudo', '-S'] + current_tx_cmd.split(), capture_output=True, text=True)
            
            curr_tx_val = p.stdout
            curr_tx_val_f = round(float(curr_tx_val), 2)
            
            print('Done!')
            return curr_tx_val_f, 200


@monitoring.route('/XRCurrentRxPowerGet/<string:interface>')
@monitoring.response(200, 'Success')
class _XR_current_RX_power(Resource):
    @monitoring.doc(description=" XR current RX power monitoring")
    @staticmethod
    def get(interface):
            global sudo_password
            if 'channel' in interface:
                [p, eth_num] = interface.split('-')
                interface = f"Ethernet{eth_num}"
                port_id = port_mapping_xr(eth_num)

            elif 'net' in interface:
                [p, eth_num] = interface.split('net')
                #print(p, eth_num)
                port_id = port_mapping_xr(eth_num)
                #print(port_id)
            else:
                return "Please specify a valid channel or Ethernet value", 404


            current_rx_cmd = f"bash /home/admin/xr_control/xr_config_monitoring.sh -c {port_id}"
            print(f"Running command: {current_rx_cmd}")


            p = subprocess.run(['sudo', '-S'] + current_rx_cmd.split(), capture_output=True, text=True)
            
            curr_rx_val = p.stdout
            curr_rx_val_f = round(float(curr_rx_val), 2)
            
            print('Done!')
            return curr_rx_val_f, 200


@monitoring.route('/XRConfiguredFrequencyGet/<string:interface>')
@monitoring.response(200, 'Success')
class _XR_configured_frequency(Resource):
    @monitoring.doc(description=" XR configured frequency monitoring")
    @staticmethod
    def get(interface):
            global sudo_password
            if 'channel' in interface:
                [p, eth_num] = interface.split('-')
                interface = f"Ethernet{eth_num}"
                port_id = port_mapping_xr(eth_num)

            elif 'net' in interface:
                [p, eth_num] = interface.split('net')
                #print(p, eth_num)
                port_id = port_mapping_xr(eth_num)
                #print(port_id)
            else:
                return "Please specify a valid channel or Ethernet value", 404


            configured_freq_cmd = f"bash /home/admin/xr_control/xr_config_monitoring.sh -e {port_id}"
            print(f"Running command: {configured_freq_cmd}")


            p = subprocess.run(['sudo', '-S'] + configured_freq_cmd.split(), capture_output=True, text=True)
            
            freq_val = p.stdout
            freq_val_f = round(float(freq_val), 6)
            freq_val_mhz = freq_val_f * 1000000            

            print('Done!')
            return int(freq_val_mhz), 200

@monitoring.route('/XRCurrentFrequencyGet/<string:interface>')
@monitoring.response(200, 'Success')
class _XR_current_frequency(Resource):
    @monitoring.doc(description=" XR current frequency monitoring")
    @staticmethod
    def get(interface):
            global sudo_password
            if 'channel' in interface:
                [p, eth_num] = interface.split('-')
                interface = f"Ethernet{eth_num}"
                port_id = port_mapping_xr(eth_num)

            elif 'net' in interface:
                [p, eth_num] = interface.split('net')
                #print(p, eth_num)
                port_id = port_mapping_xr(eth_num)
                #print(port_id)
            else:
                return "Please specify a valid channel or Ethernet value", 404


            curr_freq_cmd = f"bash /home/admin/xr_control/xr_config_monitoring.sh -f {port_id}"
            print(f"Running command: {curr_freq_cmd}")


            p = subprocess.run(['sudo', '-S'] + curr_freq_cmd.split(), capture_output=True, text=True)
            
            curr_freq_val = p.stdout
            curr_freq_val_f = round(float(curr_freq_val), 6)
            curr_freq_val_mhz = curr_freq_val_f * 1000000            

            print('Done!')
            return int(curr_freq_val_mhz), 200


@monitoring.route('/XR_OSNR_Get/<string:interface>/<int:group_id>')
@monitoring.response(200, 'Success')
class _XR_osnr(Resource):
    @monitoring.doc(description=" XR OSNR monitoring")
    @staticmethod
    def get(interface, group_id):
            global sudo_password
            if 'channel' in interface:
                [p, eth_num] = interface.split('-')
                interface = f"Ethernet{eth_num}"
                port_id = port_mapping_xr(eth_num)

            elif 'net' in interface:
                [p, eth_num] = interface.split('net')
                #print(p, eth_num)
                port_id = port_mapping_xr(eth_num)
                #print(port_id)
            else:
                return "Please specify a valid channel or Ethernet value", 404

            if group_id == 1:
                electrical_lane = 1
            elif group_id == 2:
                electrical_lane = 3
            elif group_id == 3:
                electrical_lane = 5
            elif group_id == 4:
                electrical_lane = 7
            else:
                return "Please specify a valid group id", 404


            get_osnr_cmd = f"bash /home/admin/xr_control/xr_config_monitoring.sh -g {port_id},{electrical_lane}"
            print(f"Running command: {get_osnr_cmd}")


            p = subprocess.run(['sudo', '-S'] + get_osnr_cmd.split(), capture_output=True, text=True)
            
            osnr_val = p.stdout
            osnr_val_f = round(float(osnr_val), 2)          

            print('Done!')
            return osnr_val_f, 200


@monitoring.route('/XR_pre_fec_ber_Get/<string:interface>/<int:group_id>')
@monitoring.response(200, 'Success')
class _XR_ber(Resource):
    @monitoring.doc(description=" XR pre-FEC-BER monitoring")
    @staticmethod
    def get(interface, group_id):
            global sudo_password
            if 'channel' in interface:
                [p, eth_num] = interface.split('-')
                interface = f"Ethernet{eth_num}"
                port_id = port_mapping_xr(eth_num)

            elif 'net' in interface:
                [p, eth_num] = interface.split('net')
                #print(p, eth_num)
                port_id = port_mapping_xr(eth_num)
                #print(port_id)
            else:
                return "Please specify a valid channel or Ethernet value", 404

            if group_id == 1:
                electrical_lane = 1
            elif group_id == 2:
                electrical_lane = 3
            elif group_id == 3:
                electrical_lane = 5
            elif group_id == 4:
                electrical_lane = 7
            else:
                return "Please specify a valid group id", 404


            get_ber_cmd = f"bash /home/admin/xr_control/xr_config_monitoring.sh -h {port_id},{electrical_lane}"
            print(f"Running command: {get_ber_cmd}")


            p = subprocess.run(['sudo', '-S'] + get_ber_cmd.split(), capture_output=True, text=True)
            
            ber_val = p.stdout
            ber_val_f = round(float(ber_val), 6)          

            print('Done!')
            return ber_val_f, 200


@monitoring.route('/getDdataValues/<string:interface>/<int:mode>/<string:typex>')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _getData2(Resource):
    @staticmethod
    def get(interface, mode, typex):
       lines = []
       pport = port_mapping(interface)
       platform_chassis = sonic_platform.platform.Platform().get_chassis()
       platform_sfputil = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper()
       sfp = platform_chassis.get_sfp(int(pport))
       apix = sfp.get_xcvr_api()
       r = redis.Redis(host='localhost', port=6379, db=6)
       for i in range (0, mode):
           d1 = r.hgetall(TRANSCEIVER_DOM_SENSOR_TABLE + '|' + interface)
           d = {k.decode('utf8'): v.decode('utf8') for k, v in d1.items()}
           if typex == "TX":
               tx = round(float(d['tx_curr_power']), 2)
               rx_tot = round(float(d['rx_tot_power']), 2)
               rx_sig = round(float(d['rx_sig_power']), 2)
               vals = CmisApi.get_vdm(apix)
               ber = round(float(vals['Pre-FEC BER Current Value Media Input'][1][0]),6)
               osnr = round(float(vals['OSNR [dB]'][1][0]), 2)
               esnr = round(float(vals['eSNR [dB]'][1][0]),2)
               line = "{},{},{},{},{},{}".format(tx, rx_tot, rx_sig, ber, osnr, esnr)
               lines.append(line)
           elif typex == "EDFA":
               tx = round(float(d['txpower']), 2)
               rx = round(float(d['rxpower']), 2)
               gain = round(float(d['gain_report']), 2)
               line = "{},{},{}".format(tx, rx, gain)
               lines.append(line)
           print(line)
       return lines, 200


@monitoring.route('/startKafkaTelemetry/<string:interface>')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _startTelemetry(Resource):
    @monitoring.doc(description="start kafka telemetry")
    @staticmethod
    def put(interface):
        global threads
        global thread_id
        global jobs

        event = Event()

        thread = Thread(target=kafka_task, args=(event, thread_id, interface))
        thread.start()

        threads[thread_id] = {}
        jobs[thread_id] = {}
        threads[thread_id]["event"] = event
        threads[thread_id]["thread"] = thread
        threads[thread_id]["active"] = True
        jobs[thread_id]["data"] = [interface]
        jobs[thread_id]["active"] = True
        thread_id = thread_id + 1
        return thread_id - 1, 200


@monitoring.route('/startTelemetry/<string:interface>/<int:mode>')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _startTelemetry(Resource):
    @monitoring.doc(description="start telemetry")
    @staticmethod
    def put(interface, mode):
        global threads
        global thread_id
        global jobs

        event = Event()

        thread = Thread(target=telemetry_task, args=(event, thread_id, interface, mode))
        thread.start()

        threads[thread_id] = {}
        jobs[thread_id] = {}
        threads[thread_id]["event"] = event
        threads[thread_id]["thread"] = thread
        threads[thread_id]["active"] = True
        jobs[thread_id]["data"] = [interface, mode]
        jobs[thread_id]["active"] = True
        thread_id = thread_id + 1
        return thread_id - 1, 200

@monitoring.route('/stopTelemetry/<int:job_id>')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _stopTelemetryData(Resource):
    @monitoring.doc(description="stop telemetry")
    @staticmethod
    def delete(job_id):
        global threads
        global thread_id
        global jobs
        if threads[job_id]["active"]: 
            event = threads[job_id]["event"]
            thread = threads[job_id]["thread"]
            event.set()
            # wait for the new thread to finish
            thread.join()
            threads[job_id]["active"] = False
            jobs[job_id]["active"] = False
            return job_id , 200
        return thread_id , 404




@monitoring.route('/getTelemetryJobs')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _getTelemetry(Resource):
    @staticmethod
    def get():
        global jobs
        return jobs, 200


if __name__ == '__main__':
    c_file = open(config_file)
    config = json.load(c_file)
    print(config)
    app.run(host='0.0.0.0', port=portx)


