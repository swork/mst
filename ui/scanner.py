#! /usr/local/bin/python

import wx
import wx.grid
from db import Db, DatetimeAsTimestring
import weakref
import re
from ui.activitytable import ActivityTable

trace = True

def alert():
    wx.Sound.PlaySound("alert.wav", wx.SOUND_ASYNC)

class ActivityGrid(wx.grid.Grid):
    def __init__(self, parent, db):
        wx.grid.Grid.__init__(self, parent, -1)
        self.parent = parent
        table = ActivityTable(db, self) # onlySinceEmpty=True)
        self.SetTable(table, True)
        self.EnableEditing(False)
        self.SetRowLabelSize(40)
        self.SetMargins(0,0)
        self.EnableDragRowSize(False)

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
        wx.Frame.__init__(self, parent, id, title, size=(500,600))
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

        self.grid = ActivityGrid(self, db)

        self.bibField = wx.TextCtrl(self)
#         self.bibField.SetDefault()
#        self.Bind(wx.EVT_TEXT_FIELD_CHANGED_FAKE, self.RecordBib)
#         reportButton = wx.Button(self)
#         reportButton.SetDefault()
#         reportButton.SetLabel("Click Here to record a finish impulse")
#         self.Bind(wx.EVT_BUTTON, self.RecordImpulse)

        boxSizer = wx.BoxSizer(wx.VERTICAL)
        boxSizer.Add(self.grid, 100, wx.EXPAND)
        boxSizer.Add(self.bibField, 0, wx.EXPAND)
        self.SetSizer(boxSizer)

        self.Show(True)

    def RecordBib(self, id):
        self.db.RecordBib()
        self.Refresh()

    def Refresh(self):
        self.grid.Reload()

    def OnAbout(self, evt):
        dlg = wx.MessageDialog(self, "Record Bib Scans", "About", wx.OK)
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

