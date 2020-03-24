# !/usr/bin/env python3
# Joshua DeMoss
# Project 2 - RDT
# 3/24/20
# 
# Purpose: Construct a Reliable Data Transfer Protocol from Scratch
# using the given network simulator


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
        
        # Source Port of this Socket
        self.sPort = None
        
        # Destination Port once connected to another socket
        self.dPort = None
        
        # Destination IP address once " " " "
        self.dIP = None
        
        # Indicates if this socket is currently connected to another socket
        self.connected = False

        # Used to distinguish packets between each other 1 = SYN, 2 = SYN ACK, 3 = ACK, 0 = Regular Message
        self.flag = 0

        # Used to inform the "sending" socket whether it it's sent data was recieved
        self.acked = False

    
    # Inherited methods:
        # deliver() -  adds to buffer
        # recv(n) -  rectrives/ returns up to n bytes from buffer
    
    # Binds this socket to a port number
    def bind(self, port): # only new definition - the rest are overrides of super class
        
        # will be true if connect() was called or makenewsocket() is called in accept()
        if self.connected: 
            raise StreamSocket.AlreadyConnected

        # Checks to see if port has been used on this socket's host
        elif port in self.proto.usedPorts and self.proto.usedPorts[port][0] == self.proto.host.ip: 
            raise StreamSocket.AddressInUse
    
        self.sPort = port
        self.proto.usedPorts[port] = [self.proto.host.ip, self] # add port to protocol's used ports dictionary

    # Qualifies this socket as a listening socket
    def listen(self):
        if self.sPort == None:
            raise StreamSocket.NotBound
        elif self.connected:
            raise StreamSocket.AlreadyConnected
        
        self.proto.listeningPorts.add(self.sPort)
    
    # Retrieves next request from request queue, makes a new socket, connects the new socket to the requesting socket   
    def accept(self):
        if self.sPort not in self.proto.listeningPorts:
            raise StreamSocket.NotListening
        
        addr = self.requests.get() # get info from request queue
        s = self.proto.makeNewSocket(addr[1], self.sPort, addr[0]) # make a new socket w that info
        
        s.sendACK(2)
        self.proto.connSockets[(addr[1], self.sPort, addr[0])][1] = 1 # set new socket's seq number to 1 (it recieved a 0 in the connect packet)
        return (s, (addr[0], addr[1]))

    # Makes Connection request to destination socket
    def connect(self, addr):
        if self.connected:
            raise StreamSocket.AlreadyConnected
        elif self.sPort in self.proto.listeningPorts:
            raise StreamSocket.AlreadyListening

        self.connected = True
        if self.sPort == None: # Select a random port number for the socket 
            randPort = random.randrange(49152, 65535)
            while randPort in self.proto.usedPorts:
                randPort = random.randrange(49152, 65535)
            self.sPort = randPort
            self.proto.usedPorts[self.sPort] = [self.proto.host.ip, self]

        self.dIP = addr[0]
        self.dPort = addr[1]
        self.sendACK(1) #used to make the initial connection request

    # Used to send data between Sockets
    def send(self, data):
        if not self.connected:
            raise StreamSocket.NotConnected


        if self.flag == 1 or self.flag == 2: # If this packet is a SYN or SYN ACK packet
            seqNum = 0
        else: #Packet is an ACK or reg msg
            seqNum = self.proto.connSockets[(self.dPort, self.sPort, self.dIP)][1] # get the cur seq num of the socket
        
        checksum = self.proto.checksum(self.sPort, self.dPort, seqNum, self.flag, data)   
        hdr = self.proto.packHeader(self.sPort, self.dPort, seqNum, self.flag, checksum) # 20 bytes of data

        
        if self.flag == 2 or self.flag == 3: # If packet is a SYN ACK or reg ACK
            self.output(hdr+data, self.dIP)
        else:
            # Wait till this socket recieves an ACK before exiting the fun call
            while not self.acked:
                self.output(hdr+data, self.dIP)
                start = time.time()
                while time.time() - start < .01:
                    if self.acked:
                        break
            self.acked = False
       
        if self.flag != 1: # Update the sequence number afterwards
            self.proto.connSockets[(self.dPort, self.sPort, self.dIP)][1] = 1 - seqNum

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
        
        # Dictionary of all connections on this host
        self.connSockets = {} #(sPort, dPort, sIP)

        # Dictionary of used ports on this host
        self.usedPorts = {}

        # Set of listening ports
        self.listeningPorts = set()

    def input(self, seg, host):
        sPort, dPort, seqNum, flag, checksum, data = self.parseRDT(seg)

        if checksum == self.checksum(sPort, dPort, seqNum, flag, data):
            if flag == 0: #if its a regular message
                if (sPort, dPort, host) in self.connSockets:
                    correctSocket = self.connSockets[(sPort, dPort, host)][0]
                    if seqNum == self.connSockets[(sPort, dPort, host)][1]:
                        correctSocket.deliver(data)
                        correctSocket.sendACK(3)
                    else:
                        self.connSockets[(sPort, dPort, host)][1] = 1 - self.connSockets[(sPort, dPort, host)][1]
                        correctSocket.sendACK(3)
            else: # SYN or ACK message
                if dPort in self.usedPorts:
                    correctSocket = self.usedPorts[dPort][1]
                    if flag == 1: # SYN request
                        if ((host, sPort) not in list(correctSocket.requests.queue)) and ((sPort, dPort, host) not in self.connSockets): #not in queue or connSockets
                            correctSocket.requests.put((host, sPort)) #
                        elif (host, sPort) not in list(correctSocket.requests.queue): #if the connection is already made (queue doesn't contain it though)
                            correctSocket = self.connSockets[(sPort, dPort, host)][0]
                            self.connSockets[(sPort, dPort, host)][1] = 1 - self.connSockets[(sPort, dPort, host)][1] #get the opposite sequence number of that connection
                            correctSocket.sendACK(2) #use that sequence number to send an ACK
                            
                    elif flag == 2: # SYN ACK
                        self.connSockets[(sPort, dPort, host)] = [correctSocket, 1]
                        correctSocket.acked = True # will be set false again by send
                    
                    elif (flag == 3) and ((sPort, dPort, host) in self.connSockets) and (seqNum == self.connSockets[(sPort, dPort, host)][1]):
                        correctSocket = self.connSockets[(sPort, dPort, host)][0]
                        correctSocket.acked = True # Notify the sender that it recieved an ACK by setting acked to true

    # Helper function for accept to make a new socket
    def makeNewSocket(self, sPort, dPort, sIP):
        toReturn = RDTSocket(self)
        toReturn.connected = True
        toReturn.sPort = dPort
        toReturn.dPort = sPort
        toReturn.dIP = sIP
        self.connSockets[(sPort, dPort, sIP)] = [toReturn, 0] #reference to self and sequence number
        return toReturn

    # Helper function to help pack the header bytes
    def packHeader(self, sPort, dPort, seqNum, flag, checksum):
        sPort = sPort.to_bytes(4, 'big')
        dPort = dPort.to_bytes(4, 'big')
        seqNum = seqNum.to_bytes(4, 'big')
        flag = flag.to_bytes(4, 'big')
        checksum = checksum.to_bytes(4, 'big')
        return sPort + dPort + seqNum + flag + checksum

    # Helper function to parse the header bytes
    def parseRDT(self, seg):
        sPort = int.from_bytes(seg[0:4], "big")
        dPort = int.from_bytes(seg[4:8], "big")
        seqNum = int.from_bytes(seg[8:12], "big")
        flag = int.from_bytes(seg[12:16], "big")
        checksum = int.from_bytes(seg[16:20], "big")
        data = seg[20:]
        return sPort, dPort, seqNum, flag, checksum, data

    # Helper function to creat the checksum
    def checksum(self, sPort, dPort, seqNum, flag, data):
        return (sPort + dPort + flag + sum(data)) % ((2 ** 32) - 1)