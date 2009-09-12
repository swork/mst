import thread
import socket
import types

INADDR_BC = '<broadcast>'
HEAR_PORT = 1793
BIND_ADDRESS = ''               # default, see ~/.mst for override

class Said(object):
    SAY_PORT = 0                # until we first Say

class Say(object):
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        opt = self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        print "notifier sending Awake!"
        self.sock.sendto("Awake!", 0, (INADDR_BC, HEAR_PORT))
        address = self.sock.getsockname()
        Said.SAY_PORT = address[1] # late binding!

    def NotifyAll(self):
        """Spray a notice."""
        print "notifier sending Update!"
        self.sock.sendto("Update!", 0, (INADDR_BC, HEAR_PORT))

