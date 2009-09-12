#! /usr/local/bin/python

import wx
import wx.grid
from ui.activitytable import ActivityTable
import notify
import serialtimer

trace = True

def alert():
    wx.Sound.PlaySound("alert.wav", wx.SOUND_ASYNC)

class ActivityGrid(wx.grid.Grid):
    def __init__(self, parent, db, button_id):
        wx.grid.Grid.__init__(self, parent, -1)
        self.parent = parent
        table = ActivityTable(db, self, onlySinceEmpty = True)
        self.button_id = button_id
        self.SetTable(table, True)
        self.EnableEditing(False)
        self.SetRowLabelSize(40)
        self.SetMargins(0,0)
        self.EnableDragRowSize(False)
        wx.grid.EVT_GRID_CELL_RIGHT_CLICK(self,self.OnGridRightClick)
        #self.SetCanFocus(false) # not implemented in this framework port

    def AcceptsFocus(self):
        return False            # no effect seen
    def AcceptsFocusFromKeyboard(self):
        return False            # no effect seen
    def AcceptsFocusRecursively(self):
        return False            # no effect seen
    def SetFocus(self):
        button = self.parent.FindWindow(self.button_id)
        print "SF found button ", button
        if button:
            button.SetFocus()   # no effect seen

    def OnGridRightClick(self, evt):
        print "right click %d,%d" % (evt.GetRow(), evt.GetCol())
        self.ctxRow = evt.GetRow() # for handlers
        self.ctxCol = evt.GetCol()
        self.SetGridCursor(self.ctxRow, self.ctxCol)

        # only bind events once; could have done this way up top.
        if not hasattr(self, "ctxEraseImpulse"):
            self.ctxEraseImpulse = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnCtxEraseImpulse,
                      id=self.ctxEraseImpulse)

        menu = wx.Menu()
        item = wx.MenuItem(menu, self.ctxEraseImpulse, "Erase This Impulse")
        menu.AppendItem(item)

        self.PopupMenu(menu)
        menu.Destroy()

    def OnCtxEraseImpulse(self, evt):
        self.GetTable().EraseImpulse(self.ctxRow)

    def GetColumnWidthsSum(self):
        n = self.GetNumberCols()
        width = self.GetRowLabelSize() + 1 # include border, ugh
        for i in range(0,n):
            w = self.GetColSize(i) + 1
            width += w
            if trace: print "width col %d is %d" % (i, w)
        return width + 1

    def Reload(self):
        self.GetTable().Reload()

class MainFrame(wx.Frame):
    ID_EASY = 43
    def __init__(self, parent, id, title, db):
        wx.Frame.__init__(self, parent, id, title, size=(400,500))
        self.db = db
        self.click_counter = 0

        self.CreateStatusBar()
        self.UpdateStatusBar()

        menuBar = wx.MenuBar(wx.MB_DOCKABLE)
        fileMenu = wx.Menu()

        editMenu = wx.Menu()
        editMenu.Append(wx.ID_UNDO, "&Undo\tCtrl-Z", "Not yet implemented")
        editMenu.Append(wx.ID_REDO, "Redo\tShift-Ctrl-Z", "Not yet implemented")

        helpMenu = wx.Menu()
        helpMenu.Append(wx.ID_ABOUT, "&About")
        helpMenu.Append(wx.ID_ANY, "&Other")

        menuBar.Append(fileMenu, "&File")
        menuBar.Append(editMenu, "&Edit")
        menuBar.Append(helpMenu, "&Help")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)
        self.Bind(wx.EVT_MENU, self.OnQuit, id=wx.ID_EXIT)

        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        button_id = wx.NewId()
        reportButton = wx.Button(self, id=button_id)
        self.grid = ActivityGrid(self, db, button_id)

        reportButton.SetDefault()
        reportButton.SetLabel("Click Here to record a finish impulse")
        self.Bind(wx.EVT_BUTTON, self.RecordImpulse)

        boxSizer = wx.BoxSizer(wx.VERTICAL)
        boxSizer.Add(self.grid, 100, wx.EXPAND)
        boxSizer.Add(reportButton, 0, wx.EXPAND)
        self.SetSizer(boxSizer)

        self.hearer = notify.Hear(self)
        self.Bind(notify.EVT_UPDATE_INFO, self.OnHeardNotify)

        self.serialtimer = serialtimer.RelayImpulses(self)
        self.Bind(serialtimer.EVT_SERIAL_IMPULSES, self.OnHeardSerialImpulse)

        self.Show(True)
        reportButton.SetFocus()

    def __del__(self):
        self.hearer.keepGoing = False

    def RecordImpulse(self, id):
        self.db.RecordImpulse()
        self.click_counter += 1
        self.SetStatusText("Click %d" % self.click_counter)
        self.Refresh()

    def OnHeardSerialImpulse(self, evt):
        self.db.RecordImpulses(evt.times)
        self.Refresh()

    def Refresh(self):
        self.grid.Reload()

    def OnHeardNotify(self, evt):
        print "Heard msg:%s mine:" % evt.message, evt.likelyFromMe
        if not evt.likelyFromMe:
            self.Refresh()

    def OnAbout(self, evt):
        dlg = wx.MessageDialog(self, "Record Finish Impulses", "About", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnQuit(self, evt):
        closeme = False
        dlg = wx.MessageDialog(self, u"Quit: Are you sure?",
                                   "Quit",
                                   wx.YES_NO |
                                   wx.NO_DEFAULT | 
                                   wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            closeme = True
        if closeme:
            dlg.Destroy()
            self.Destroy()

    def UpdateStatusBar(self):
        self.SetStatusText("Hello.") # self.control.GetStatusBarText())

if __name__ == "__main__":
    db = Db('sqlite:///:memory:', echo=False)
    db.LoadTestData()
    db.session.commit()

#    set = { "impulse": 2 }
#    db.session.query(Db.Scan).filter("bib = 101").update(set)
#    db.session.commit()

    app = MSTEditorApp()
    app.MainLoop()

