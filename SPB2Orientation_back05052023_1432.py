#!/usr/bin/python

import sys, pygame, socket, re
from time import sleep, gmtime, strptime
from ponycube import Screen, Cube, Quaternion
from influxdb import InfluxDBClient

BUFSIZE = 4096

defaultQuery = """SELECT "instance", "value" FROM "HKB" 
                  WHERE ("metric" = 'quaternions' AND 
                         time > now()-2s)"""

rawGyroQuery = """SELECT "instance", "value" FROM "HKB" 
                  WHERE ("metric" = 'position' AND time > now()-2s)"""

rawAccelQuery = """SELECT "instance", "value" FROM "HKB" 
                   WHERE ("metric" = 'acceleration' AND time > now()-2s)"""

numericPattern = "([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)*)"
comptQuatPattern = (f"Q{numericPattern},{numericPattern},"
                    f"{numericPattern},{numericPattern}E")
comptQuatRegex = re.compile(comptQuatPattern)

def toSigned(n,bits):
    n = n & (2**bits)-1
    return n | (-(n & (1 << (bits-1))))

def getCompleteSubSequence(sequence, instances, keyword = 'instance'):
    retVal = []
    i = 0
    j = 0
    t0 = None
    seq = sequence.copy()

    while(i < len(sequence)):
        s = seq.pop(0)

        t1 = strptime(s['time'],"%Y-%m-%dT%H:%M:%S.%fZ")

        if s[keyword] != instances[j]:
            i = i + 1
            continue

        if t0 is None:
            t0 = strptime(s['time'],"%Y-%m-%dT%H:%M:%S.%fZ")

        i = i + 1
        j = (j + 1)%len(instances)
        retVal.append(s)

        if (s[keyword] == instances[-1]) and (t1.tm_sec - t0.tm_sec <= 1.0):
            return retVal
    
    return None

class packet_reader(object):
    def __init__(self, influxHost, influxQuery = defaultQuery,
                 quat_delegate = None, imuConvHost = None, logFileName = None):
        
        self.influx = InfluxDBClient(host=influxHost, port=8086, database='spbmonitor')

        if quat_delegate:
            self.quat_delegate = quat_delegate
        else:
            self.quat_delegate = empty_packet_delegate()


        tm = gmtime()

        self.packets = []
        self.length = 0
        self.influxQuery = influxQuery
        self.imuConv = None
        self.logFileName = (f"{logFileName}-{tm.tm_year}{tm.tm_mon}"
                            f"{tm.tm_mday}-{tm.tm_hour}{tm.tm_min}{tm.tm_sec}"
                            ".dat")
        self.quatsArr = None
        self.comptQuats = None

        if imuConvHost is not None:
            imuConvSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            imuConvSocket.connect((imuConvHost, 5000))
            
            welcomeStr = b''
            if imuConvSocket is not None:
                welcomeStr = imuConvSocket.recv(1024)
            
            if welcomeStr == b'Imu conv':
                print("Imu converter ready")
                
                self.imuConv = imuConvSocket

    def read(self):
        quatsArr = None
        gyroArr = None
        accelArr = None
        comptQuats = None

        queryRes = list(self.influx.query(self.influxQuery).get_points())
        rawGyroQueryRes = list(self.influx.query(rawGyroQuery).get_points())
        rawAccelQueryRes = list(self.influx.query(rawAccelQuery).get_points())

        subSeq = getCompleteSubSequence(queryRes, ['q1','q2','q3','q4'])

        gyroSubSeq = getCompleteSubSequence(rawGyroQueryRes, ['X','Y','Z'])

        accelSubSeq = getCompleteSubSequence(rawAccelQueryRes, ['X','Y','Z'])
        
        if subSeq is not None:
            quatsArr = [q['value'] for q in subSeq]

        gyroStr = ""
        if gyroSubSeq is not None:
            gyroArr = [toSigned(int(g['value']),16) for g in gyroSubSeq]
            gyroStr = f"{gyroArr[0]},{gyroArr[1]},{gyroArr[2]}"

        accelStr = ""
        if accelSubSeq is not None:
            accelArr = [toSigned(int(a['value']),16) for a in accelSubSeq]
            accelStr = f"{accelArr[0]},{accelArr[1]},{accelArr[2]}"

        if self.imuConv is not None and gyroStr != "" and accelStr != "":
            self.imuConv.send(f"{gyroStr},{accelStr}\n".encode('utf-8'))

            recvData = self.imuConv.recv(1024)

            comptQuatsFound = comptQuatRegex.findall(recvData.decode('utf-8'))

            if comptQuatsFound is not None:
                comptQuats = [float(q) for q in comptQuatsFound[0]]

        self.quatsArr = quatsArr
        self.comptQuats = comptQuats

        self.quat_delegate.dispatch((quatsArr,gyroArr,accelArr,comptQuats))

    def write_log(self):
        with open(self.logFileName,'a+') as f:
            if (self.quatsArr is not None) and (self.comptQuats is not None):
                
                dStr = (f"{','.join(str(q) for q in self.quatsArr)},"
                        f"{','.join(str(q) for q in self.comptQuats)},"
                        f"{','.join(str(q1-q0) for q1,q0 in zip(self.quatsArr,self.comptQuats))}\n")

                f.write(dStr)

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
        self.rawGyro = None
        self.rawAccel = None
        self.comptQuats = None

    def loop(self,event):
        if self.latest is not None:
            packet = quat_packet(self.latest)

            q = packet.to_q().normalized()
            
            print(f"q0 = {self.latest[0]}, q1 = {self.latest[1]}, "
                  f"q2 = {self.latest[2]}, q3 = {self.latest[3]}")
            
            if self.rawGyro is not None:
                print(f"rgX = {self.rawGyro[0]}, rgY = {self.rawGyro[1]}, rgZ = {self.rawGyro[2]}")

            if self.rawAccel is not None:
                print(f"raX = {self.rawAccel[0]}, raY = {self.rawAccel[1]}, raZ = {self.rawAccel[2]}\n")

            if self.comptQuats is not None:
                print(f"cQ0 = {self.comptQuats[0]}, cQ1 = {self.comptQuats[1]}, "
                      f"cQ2 = {self.comptQuats[2]}, cQ3 = {self.comptQuats[3]}")

            self.cube.erase(self.screen)

            self.cube.draw(self.screen,q)

            pygame.display.flip()

            self.latest = None
            
            sleep(1)

    def dispatch(self,p):
        self.latest = p[3]#p[0]
        self.rawGyro = p[1]
        self.rawAccel = p[2]
        self.comptQuats = p[0]#p[3]

class quat_packet(object):
    def __init__(self, l):
        self.q0 = l[0]
        self.q1 = l[1]
        self.q2 = l[2]
        self.q3 = l[3]

    def to_q(self):
        return Quaternion(self.q0, self.q1, self.q2, self.q3)

if __name__ == "__main__":
    imuConvHost = None
    logFileName = None

    argc = len(sys.argv)

    if argc == 2:
        influxHost = sys.argv[1]
        influxQ = defaultQuery
    elif argc == 3:
        influxHost = sys.argv[1]
        influxQ = sys.argv[2]
    elif argc == 4:
        influxHost = sys.argv[1]
        influxQ = sys.argv[2] if sys.argv[2] != "default" else defaultQuery
        imuConvHost = sys.argv[3]
    elif argc == 5:
        influxHost = sys.argv[1]
        influxQ = sys.argv[2] if sys.argv[2] != "default" else defaultQuery
        imuConvHost = sys.argv[3]
        logFileName = sys.argv[4]
    else:
        print("usage: " + sys.argv[0] + " influxDB-Host [default|QUERY] [imuConv-Host] [logFile]")
        sys.exit(-1)

    pygame.init()

    viewer = cube_packet_viewer()

    reader = packet_reader(influxHost, 
                           quat_delegate = viewer,
                           influxQuery = influxQ,
                           imuConvHost = imuConvHost,
                           logFileName = logFileName)

    while 1:
        event = pygame.event.poll()

        if event.type == pygame.QUIT:
            viewer.close()
            break

        reader.read()
        
        reader.write_log()

        viewer.loop(event)
