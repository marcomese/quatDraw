#!/usr/bin/python

import sys, pygame
from time import sleep
from ponycube import Screen, Cube, Quaternion
import re
from influxdb import InfluxDBClient
import numpy as np

BUFSIZE = 4096

numPattern = "[+-]?\d*.?\d*"
dataPattern = f"Q({numPattern}),({numPattern}),({numPattern}),({numPattern})\n"

dataRegex = re.compile(dataPattern)

class eMPL_packet_reader(object):
    def __init__(self, influxHost, quat_delegate=None):
        self.quatsBuffer = []

        self.influx = InfluxDBClient(host=influxHost, port=8086, database='spbmonitor')

        if quat_delegate:
            self.quat_delegate = quat_delegate
        else:
            self.quat_delegate = empty_packet_delegate()


        self.packets = []
        self.length = 0

    def read(self):
        if self.quatsBuffer == [] or self.quatsBuffer is None:
            queryRes = self.influx.query("""SELECT "instance", "value" FROM "HKB" WHERE ("metric" = 'quaternions' AND time > '2023-04-20T18:00:00Z' AND time < '2023-04-20T18:30:00Z')""")#"""SELECT "instance", "value" FROM "HKB" 
                                         #   WHERE ("metric" = 'quaternions' AND 
                                         #          time > now()-2s)""")
                                            
        
            quats = [[q['value'] for q in queryRes.get_points() if q['instance'] == f"q{i}"] 
                     for i in range(1,5)]
        
            quatsArr = np.asarray(quats).T
        
            self.quatsBuffer = quatsArr.tolist()

            self.quat_delegate.dispatch(self.quatsBuffer) 

    def write_log(self,fname):
        f = open(fname,'w')

        for p in self.packets:
            f.write(p.logfile_line())

        f.close()

class empty_packet_delegate(object):
    def loop(self,event):
        pass

    def dispatch(self,p):
        pass

class cube_packet_viewer(object):
    def __init__(self):
        self.screen = Screen(480,400,scale=1.5)
        self.cube = Cube(30,60,10)
        self.q = Quaternion(1,0,0,0)
        self.latest = None

    def loop(self,event):
        packet = None

        if (self.latest != []) and self.latest is not None:
            lat = self.latest.pop(0)
            
            if len(lat) == 4:
                packet = quat_packet(lat)
        
        if packet is not None:
            q = packet.to_q().normalized()

            self.cube.erase(self.screen)

            self.cube.draw(self.screen,q)

            pygame.display.flip()

            sleep(1)

            # self.latest = None

    def dispatch(self,p):
        self.latest = p

class quat_packet(object):
    def __init__(self, l):
        self.q0 = l[0]
        self.q1 = l[1]
        self.q2 = l[2]
        self.q3 = l[3]

        print(f"q0 = {self.q0}, q1 = {self.q1}, q2 = {self.q2}, q3 = {self.q3}")

    def to_q(self):
        return Quaternion(self.q0, self.q1, self.q2, self.q3)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        influxHost = sys.argv[1]
    else:
        print("usage: " + sys.argv[0] + " influxDB-Host")
        sys.exit(-1)

    pygame.init()

    viewer = cube_packet_viewer()

    reader = eMPL_packet_reader(influxHost, quat_delegate = viewer)

    while 1:
        event = pygame.event.poll()

        if event.type == pygame.QUIT:
            viewer.close()
            break

        reader.read()

        viewer.loop(event)
