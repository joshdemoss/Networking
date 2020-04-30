# RDT.py

The purpose of this project is to design a custom transport layer protocol that will providing reliable communication over an 
unreliable medium. This was done by implementing standard protocol and socket functions for a reliable transport protocol 
called RDT. The project structure is intentionally modeled after the Linux kernel’s sockets implementation, so that the code
operates very similarlly to the way that real network protocols are implemented in an operating system.

To aid in testing, the protocol runs not on a real network but on a network simulation which provides fine-grained control 
over packet corruption and loss.

Implemented files: rdt.py
