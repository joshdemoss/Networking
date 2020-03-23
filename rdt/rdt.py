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
       
        # Inherited variables: 
            # data (data)
            # datamu (lock for threading)
            # proto (protocol)

        # Connection Queue
        self.requests = Queue()
        
        # Variables
        self.sPort = None
        self.dPort = None
        self.dIP = None
        self.connected = False
        self.flag = 0
        self.acked = False

    # Inherited methods:
    # - deliver: adds to buffer
    # - recv(n) rectrives/ returns up to n bytes from buffer
    
    def bind(self, port): # only new definition
        if self.connected: # will be true if connect was called or makenewsocket() is called (in accept)
            raise StreamSocket.AlreadyConnected
        elif port in self.proto.usedPorts and self.proto.usedPorts[port][0] == self.proto.host.ip:
            raise StreamSocket.AddressInUse
    
        # print("bind: ", self.proto.host.ip, port)
        self.sPort = port
        self.proto.usedPorts[port] = [self.proto.host.ip, self] # add port to uPorts

    def listen(self):
        if self.sPort == None:
            raise StreamSocket.NotBound
        elif self.connected:
            raise StreamSocket.AlreadyConnected
        
        # print(self.sPort, "listen called")
        self.proto.listeningPorts.add(self.sPort)
        
    def accept(self):
        if self.sPort not in self.proto.listeningPorts:
            raise StreamSocket.NotListening
        
        # print(self.sPort, "accept called")
        addr = self.requests.get()
        s = self.proto.makeNewSocket(addr[1], self.sPort, addr[0])
        
        # print(self.sPort, "Sending ACK")
        s.sendACK(2)
        self.proto.connSockets[(addr[1], self.sPort, addr[0])][1] = 1 # 1 becuase it recieved a 0 in the connect packet
        return (s, (addr[0], addr[1]))

    def connect(self, addr):
        # print("connect", self.proto.host.ip, self.sPort, addr[0], addr[1])
        if self.connected:
            raise StreamSocket.AlreadyConnected
        elif self.sPort in self.proto.listeningPorts:
            raise StreamSocket.AlreadyListening

        self.connected = True
        if self.sPort == None:
            # print("random port selected")
            # randPort = random.randrange(49152, 65535)
            randPort = 5000
            while randPort in self.proto.usedPorts:
                # randPort = random.randrange(49152, 65535)
                randPort += 1
            self.sPort = randPort
            self.proto.usedPorts[self.sPort] = [self.proto.host.ip, self]

        self.dIP = addr[0]
        self.dPort = addr[1]
        self.sendACK(1) #used to make the initial connection request

    def send(self, data):
        if not self.connected:
            raise StreamSocket.NotConnected


        if self.flag == 1 or self.flag == 2:
            seqNum = 0
        else:
            seqNum = self.proto.connSockets[(self.dPort, self.sPort, self.dIP)][1]
        
        checksum = self.proto.checksum(self.sPort, self.dPort, seqNum, self.flag, data)   
        hdr = self.proto.packHeader(self.sPort, self.dPort, seqNum, self.flag, checksum)

        
        # print("send:  ", "sPort:", self.sPort, "dPort:", self.dPort, "host:", self.proto.host.ip, "data:", data, "seqNum:", seqNum, "flag:", self.flag, "checksum:", checksum)
        if self.flag == 2 or self.flag == 3:
            self.output(hdr+data, self.dIP)
        else:
            while not self.acked:
                # print(self.sPort, "sent:", data)
                self.output(hdr+data, self.dIP)
                start = time.time()
                while time.time() - start < .01:
                    if self.acked:
                        break
            # print("finished sending!\n")
            self.acked = False
       
        # print(self.sPort, "ACK - changing seqNum from ", seqNum, "to", 1 - seqNum)
        if self.flag != 1:
            self.proto.connSockets[(self.dPort, self.sPort, self.dIP)][1] = 1 - seqNum
        # print(self.sPort, "seqNum:", self.proto.connSockets[(self.dPort, self.sPort, self.dIP)][1])

    def sendACK(self, flag):
        self.flag = flag
        self.send(b'')
        self.flag = 0


# ----------------------------------------------------------------------------------------------------------------------------------------------------


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
        sPort, dPort, seqNum, flag, checksum, data = self.parseRDT(seg)
        # print("inputs:", "sPort:", sPort, "dPort:", dPort, "host:", host, "data:", seg[20:], "seqNum:", seqNum, "flag:", flag, "checksum:", checksum)

        if checksum == self.checksum(sPort, dPort, seqNum, flag, data):
            # print("checksum", checksum, self.checksum(sPort, dPort, seqNum, flag, data))
           
            if flag == 0: #if its a regular message
                if (sPort, dPort, host) in self.connSockets:
                    
                    # print("connection found", "data", data)
                    correctSocket = self.connSockets[(sPort, dPort, host)][0]
                    if seqNum == self.connSockets[(sPort, dPort, host)][1]:
                        correctSocket.deliver(data)
                        # print("delivered data:", correctSocket.data)
                        # print(correctSocket.sPort, "Sending ACK")
                        correctSocket.sendACK(3)
                    else:
                        # print("seqNum didn't match right -- resending old ACK", seqNum, self.connSockets[(sPort, dPort, host)][1])
                        self.connSockets[(sPort, dPort, host)][1] = 1 - self.connSockets[(sPort, dPort, host)][1]
                        # print("ignore the change in seq number below")
                        correctSocket.sendACK(3)
                else:
                	pass
                	# print("dropped packet... flag was ", flag)
            else: # SYN or ACK message
                
                # print("correctSocket: ", dPort)
                if dPort in self.usedPorts:
                    correctSocket = self.usedPorts[dPort][1]
                    if flag == 1: # SYN request
                        if ((host, sPort) not in list(correctSocket.requests.queue)) and ((sPort, dPort, host) not in self.connSockets): #not in queue or connSockets
                            # print("adding ", host, sPort, "to connection Queue")
                            correctSocket.requests.put((host, sPort)) #
                        else:
                            if (host, sPort) not in list(correctSocket.requests.queue): #if the connection is already in the queue and it is already connected (ACK was lost)
                                # print("Already connected -- resending old ACK", seqNum, self.connSockets[(sPort, dPort, host)][1])
                                correctSocket = self.connSockets[(sPort, dPort, host)][0] #get the right connection
                                self.connSockets[(sPort, dPort, host)][1] = 1 - self.connSockets[(sPort, dPort, host)][1] #get the opposite sequence number of that connection
                                # print("ignore the change in seq number below")
                                correctSocket.sendACK(2) #use that sequence number to send an ACK
                            else:
                                pass
                                # print("Accept hasn't been called yet... BE PATIENT")
                    elif flag == 2: # SYN ACK
                        # print("ACKED")
                        self.connSockets[(sPort, dPort, host)] = [correctSocket, 1]
                        correctSocket.acked = True # will be set false again by send
                    
                    elif (flag == 3) and ((sPort, dPort, host) in self.connSockets) and (seqNum == self.connSockets[(sPort, dPort, host)][1]):
                        correctSocket = self.connSockets[(sPort, dPort, host)][0]
                        correctSocket.acked = True # Notify the sender that it recieved an ACK by setting acked to true
                else:
                    pass
                    # print("Port number not in set of listening sockets")
        else:
            pass
            # print("Currupted Packet")


        # data = seg[20:]

    def makeNewSocket(self, sPort, dPort, sIP):
        toReturn = RDTSocket(self)
        # print("test 1")
        toReturn.connected = True
        # print("test 2")
        toReturn.sPort = dPort
        toReturn.dPort = sPort
        toReturn.dIP = sIP
        self.connSockets[(sPort, dPort, sIP)] = [toReturn, 0] #reference to self and sequence number
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
        data = seg[20:]
        return sPort, dPort, seqNum, flag, checksum, data

    def checksum(self, sPort, dPort, seqNum, flag, data):
        return (sPort + dPort + flag + sum(data)) % ((2 ** 32) - 1)



# B7_Corrupt02_ManyConns