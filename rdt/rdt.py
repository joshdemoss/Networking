# Joshua DeMoss
# Project 2
# 
# timeout = 1 milisecond
# segment format is up to you, but it can only add up to 32 bytes of header 
# info to a message



from network import Protocol, StreamSocket
import random
from queue import Queue
import time

# Reserved protocol number for experiments; see RFC 3692
IPPROTO_RDT = 0xfe



class RDTSocket(StreamSocket):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        """ Inherited variables: 
        data (data)
        datamu (lock for threading)
        proto ()
        """
        # Connection Queue
        self.requests = Queue()
        
        # usedPorts = [host.ip, self]
        self.uPorts = self.proto.usedPorts
        
        # (sPort, dPort, sIP)
        self.cSockets = self.proto.connSockets
        
        # set of listening ports
        self.lports = self.proto.listeningPorts

        # Variables
        self.sPort = None
        self.dPort = None
        self.dIP = None
        self.connected = False
        self.expSeqNum = 0
        self.flag = None


    """ 
    Inherited methods:
    - deliver: adds to buffer
    - recv(n) rectrives/ returns up to n bytes from buffer
    """

    def bind(self, port): # only new definition
        if self.connected: # will be true if connect was called or makenewsocket is called (in accept)
            raise StreamSocket.AlreadyConnected
        elif port in self.uPorts and self.uPorts[port][0] == self.proto.host.ip:
            raise StreamSocket.AddressInUse
    
        self.sPort = port
        self.uPorts[port] = [self.proto.host.ip, self] # add port to uPorts

    def listen(self):
        if self.sPort == None:
            raise StreamSocket.NotBound
        elif self.connected:
            raise StreamSocket.AlreadyConnected
        
        self.lports.add(self.sPort)
        



    def accept(self):

        # You may need to set connected to true here too!!!!!
        if self.sPort not in self.lports: # listen hasn't been called
            raise StreamSocket.NotListening
        
        addr = self.requests.get()
        if (addr[1], self.sPort, addr[0]) not in self.cSockets:
        	print("made new socket", addr[1], self.sPort, addr[0])
        	s = self.proto.makeNewSocket(addr[1], self.sPort, addr[0])
        else:
        	s = self.cSockets[(addr[1], self.sPort, addr[0])]
        print("ACK sent")
        s.sendACK(2)
        s.expSeqNum = 1
        # possible threading issue?
        return (s, (addr[0], addr[1]))

    def connect(self, addr):
        print("connect", self.proto.host.ip, self.sPort, addr[0], addr[1])
        if self.connected:
            raise StreamSocket.AlreadyConnected
        elif self.sPort in self.lports:
            raise StreamSocket.AlreadyListening

        self.connected = True
        if self.sPort == None:
            # randPort = random.randrange(49152, 65535)
            randPort = 5000
            while randPort in self.uPorts:
                # randPort = random.randrange(49152, 65535)
                randPort += 1
            self.sPort = randPort
            self.uPorts[self.sPort] = [self.proto.host.ip, self]

        self.dIP = addr[0]
        self.dPort = addr[1]
        self.seqNum = 0
        self.sendACK(1)


    def send(self, data):
        if not self.connected:
            raise StreamSocket.NotConnected

        checksum = self.proto.checksum(self.sPort, self.dPort, self.expSeqNum, self.flag)   
        hdr = self.proto.packHeader(self.sPort, self.dPort, self.expSeqNum, self.flag, checksum)

        
        if self.flag == 2 or self.flag == 3:
            self.output(hdr+data, self.dIP)
            self.expSeqNum = 1 - self.expSeqNum
        else:
            print("send:  ", "sPort", self.sPort, "dPort", self.dPort, "data", data, "seqNum", self.expSeqNum, "flag", self.flag)
            seqNum = self.expSeqNum
            self.expSeqNum = 1 - self.expSeqNum
            timedOut = True
            i = 0
            while timedOut and i < 4:
                self.output(hdr+data, self.dIP)
                start = time.time()
                while time.time() - start < .001:
                    if seqNum == self.expSeqNum:
                        timedOut = False
                        break
                print("sent again")
                i += 1


    def sendACK(self, flag):
        self.flag = flag
        self.send(b'')
        self.flag = 0


class RDTProtocol(Protocol):
    # inherits host from Protocol
    PROTO_ID = IPPROTO_RDT
    SOCKET_CLS = RDTSocket

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Other initialization here
        self.connSockets = {} #(sPort, dPort, sIP)
        self.usedPorts = {}
        self.listeningPorts = set()

    def input(self, seg, host):
        sPort, dPort, seqNum, flag, checksum = self.parseRDT(seg)
        print("inputs:", "sPort", sPort, "dPort", dPort, "data", seg[20:], "seqNum", seqNum, "flag", flag, "checksum", checksum)

        if checksum == self.checksum(sPort, dPort, seqNum, flag):
            if flag == 1: # SYN request
                correctSocket = self.usedPorts[dPort][1]
                if seqNum == correctSocket.expSeqNum:
                    correctSocket.requests.put((host, sPort))
                    correctSocket.flag = 0
                else:
                	pass
                    print("1 - seqNum != expSeqNum")
            elif flag == 2: # SYN ACK
                correctSocket = self.usedPorts[dPort][1]
                if seqNum == correctSocket.expSeqNum:
                    correctSocket.expSeqNum = 1 - correctSocket.expSeqNum
                    self.connSockets[sPort, dPort, host] = correctSocket
                else:
                	pass
                	print("2 - seqNum != expSeqNum", correctSocket.data)
            elif flag == 3: #Regular ACK
            	correctSocket = self.usedPorts[dPort][1]
            	if seqNum == correctSocket.expSeqNum: #if ack for what 
            		correctSocket.expSeqNum = 1 - correctSocket.expSeqNum
            	else:
            		pass
            		print("recieved an act for something I didnt send")
            elif flag == 0:
                if (sPort, dPort, host) in self.connSockets:
                    print("connection found", "data", seg[20:])
                    correctSocket = self.connSockets[(sPort, dPort, host)]
                    if seqNum == correctSocket.expSeqNum:
                        correctSocket.expSeqNum = 1 - correctSocket.expSeqNum
                        data = seg[20:]
                        if data is None:
                        	pass
                        	print("No data sent")
                        correctSocket.deliver(data)
                        print("server data:", correctSocket.data)
                    else:
                        correctSocket.expSeqNum = seqNum #Already got seqNum
                        correctSocket.sendACK(3)
                        correctSocket.expSeqNum = 1 - correctSocket.expSeqNum
                        print("seqNum didn't match right")
                else:
                	pass
                	print("dropped packet")
            else:
            	pass
            	print("flag was currupted")
        else:
        	pass
        	print("Currupted Packet")


        # data = seg[20:]

    def makeNewSocket(self, sPort, dPort, sIP):
        toReturn = RDTSocket(self)
        toReturn.connected = True
        toReturn.sPort = dPort
        toReturn.dPort = sPort
        toReturn.dIP = sIP
        toReturn.expSeqNum = 0
        toReturn.flag = 0

        self.connSockets[(sPort, dPort, sIP)] = toReturn
        return toReturn



    def packHeader(self, sPort, dPort, seqNum, flag, checksum):
        sPort = sPort.to_bytes(4, 'big')
        dPort = dPort.to_bytes(4, 'big')
        seqNum = seqNum.to_bytes(4, 'big')
        flag = flag.to_bytes(4, 'big')
        checksum = checksum.to_bytes(4, 'big')
        return sPort + dPort + seqNum + flag + checksum

    def parseRDT(self, seg):
        sPort = int.from_bytes(seg[0:4], "big")
        dPort = int.from_bytes(seg[4:8], "big")
        seqNum = int.from_bytes(seg[8:12], "big")
        flag = int.from_bytes(seg[12:16], "big")
        checksum = int.from_bytes(seg[16:20], "big")
        return sPort, dPort, seqNum, flag, checksum

    def checksum(self, sPort, dPort, seqNum, flag):
        return (sPort + dPort + flag) % 255




"""
Inherited methods:
- getid(class_) - returns Protocol ID
- socket() - creates instance of RDTsocket
- output(seg, dest) - host(getid(), seg, dst) -> tx(pID, seg, src, dst)

"""