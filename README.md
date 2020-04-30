# Networking Projects:

# Project 1 - Python Proxy Redux
File: proxy.py

The purpose of this project is to get more practice with using Python's socket library,
as well as reviewing the Berkeley sockets API. 

Instructions:
Redo the System's Project "Proxy Lab" but in Python, rather than C.

# Project 2 - Reliable Data Transfer
File: rdt.py

The purpose of this project is to design a custom transport layer protocol that will providing reliable communication over an unreliable medium. This was done by implementing standard protocol and socket functions for a reliable transport protocol called RDT. The project structure is intentionally modeled after the Linux kernel’s sockets implementation, so that the code operates very similarlly to the way that real network protocols are implemented in an operating system. 

To aid in testing, the protocol runs not on a real network but on a network simulation which
provides fine-grained control over packet corruption and loss.
