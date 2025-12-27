
import sys
import time
import random
import json
import time
from json import JSONEncoder


class MyMeasurement:
    def __init__(self):
        self.name = ""
        self.timestamp = ""
        self.fields = {}
        self.tags = {}

    def setName(self, name):
        self.name = name

    def setTag(self, key, value):
        self.tags[key] = value

    def setTimestamp(self, timestamp):
        self.timestamp = timestamp

    def addField(self, field_name, field_value):
        self.fields[field_name] = field_value

class MeasurementEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, MyMeasurement):
            my_dict = o.__dict__
            try:
                if my_dict["name"] and my_dict["timestamp"] and my_dict["fields"]:
                    return my_dict
                print(my_dict)
            except KeyError:
                return


