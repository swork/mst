import thread
import wx
import wx.lib.newevent
import serial
import types
import re

SERIAL_PORT = '/dev/tty.usbserial'

(SerialImpulseEvent, EVT_SERIAL_IMPULSE) = wx.lib.newevent.NewEvent()

def nocr(str):
    return re.sub("\x0D","!",str)

class RelayImpulses(object):
    """Open serial port, spin a thread to listen for timer messages and 
    record Impulse events."""
    def __init__(self, win):
        self.win = win
        self.keepGoing = True
        self.ser = serial.Serial(SERIAL_PORT, timeout=1)
        thread.start_new_thread(self.RelayThread, ())

    def RelayThread(self):
        saved = ''
        msg_re = re.compile('T.{12,13}? (\d+:\d+:\d+\.\d+)\x0D')
        sync_re = re.compile('\x0D')
        times = []
        while self.keepGoing:
            if len(times):
                print times
                if not None is self.win:
                    evt = SerialImpulseEvent(times=times)
                    wx.PostEvent(self.win, evt)
                times = []
            buffer = self.ser.read(4096)
            if buffer == '':
                continue
            #print "saved:",nocr(saved),"buffer:",nocr(buffer)
            saved += buffer

            if saved[0] == 'T': # start of message
                while True:
                    if len(saved) < 31: # 30 + CR
                        break           # get more
                    else:
                        match = msg_re.match(saved)
                        if not match:
                            print "Tossing entire buffer: ", nocr(saved)
                            saved = ''
                        else:
                            time = saved[match.start(1):match.end(1)]
                            times.append((time,))
                            saved = saved[match.end(0):]
            else:
                match = sync_re.search(saved)
                if match:
                    saved = saved[match.end():]
                else:
                    saved = ''

if __name__ == '__main__':
    import time
    r = RelayImpulses(None)
    time.sleep(200)
    r.keepGoing = False
    time.sleep(5)
