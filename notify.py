import thread
import wx
import wx.lib.newevent
import socket
import types

INADDR_BC = '<broadcast>'
HEAR_PORT = 1793
BIND_ADDRESS = ''               # default, see ~/.mst for override

(UpdateInfoEvent, EVT_UPDATE_INFO) = wx.lib.newevent.NewEvent()

class Said(object):
    SAY_PORT = 0                # until we first Say

class Hear(object):
    """Open a UDP socket and listen on a separate thread for
    broadcasts; send a wx.PostEvent notification when one is heard."""
    def __init__(self, win):
        self.win = win
        self.keepGoing = True

        if type(BIND_ADDRESS) == types.StringType:
            self.Bind(BIND_ADDRESS)
        else:
            for addr in BIND_ADDRESS:
                self.Bind(addr)
        thread.start_new_thread(self.HearerThread, ())

    def Bind(self, addr):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((addr, HEAR_PORT))

    def HearerThread(self):
        while self.keepGoing:
            (str, address) = self.sock.recvfrom(2048)
            likelyFromMe = (address[1] == Said.SAY_PORT)
            print "Heard %s, fromMe:" % str, likelyFromMe
            if __name__ != '__main__': # crashes hard when no wx
                evt = UpdateInfoEvent(message=str, likelyFromMe=likelyFromMe)
                wx.PostEvent(self.win, evt)

class Say(object):
    def __init__(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            opt = self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            print "notifier sending Awake!"
            self.sock.sendto("Awake!", 0, (INADDR_BC, HEAR_PORT))
            address = self.sock.getsockname()
            Said.SAY_PORT = address[1] # late binding!
        except:
            pass

    def NotifyAll(self):
        """Spray a notice."""
        print "notifier sending Update!"
        try:
            self.sock.sendto("Update!", 0, (INADDR_BC, HEAR_PORT))
        except:
            print "Some error, ignored (but no notify sent)"

if __name__ == '__main__':
    import time

    if False:
        s = Say()
        while True:
            s.NotifyAll()
            time.sleep(1)
    else:
        h = Hear(None)
        time.sleep(2)
        s = Say()
        s.NotifyAll()
        time.sleep(2)
        s.NotifyAll()
        time.sleep(10000)
        h.keepGoing = False


