#! /usr/local/bin/python

import wx
import wx.grid
from ui.activitytable import ActivityTable
import notify
import db

trace = True

def alert():
    wx.Sound.PlaySound("alert.wav", wx.SOUND_ASYNC)

class BibTextCtrl(wx.TextCtrl):
    def __init__(self, *args, **kwargs):
        self.recordFn = kwargs['recordFn']
        del kwargs['recordFn']
        wx.TextCtrl.__init__(self, *args, **kwargs)
        localStyles = wx.TE_PROCESS_ENTER
        self.SetWindowStyle(self.GetWindowStyle() | localStyles)
        self.Bind(wx.EVT_TEXT, self.OnText)
        self.Bind(wx.EVT_TEXT_ENTER, self.OnTextEnter)
    def OnText(self, evt):
        s = self.GetValue()
        ip = self.GetInsertionPoint()
        lasti = len(s) - 1
        iter = enumerate(s)
        try:
            i, c = next(iter, (-1,None)) # py2.6ism
        except NameError:
            try:
                i, c = iter.next()
            except StopIteration:
                i = -1
        while i != -1:
            if c < '0' or c > '9':
                ip -= 1
                if i == lasti:
                    self.SetValue(s[0:i])
                else:
                    self.SetValue(s[0:i] + s[i+1:])
            try:
                i, c = next(iter, (-1,None)) # py2.6ism
            except NameError:
                try:
                    i, c = iter.next()
                except StopIteration:
                    i = -1
        self.SetInsertionPoint(ip)
    def OnTextEnter(self, evt):
        s = evt.GetString()
        if len(s) > 0:
            self.recordFn(s)
            self.Clear()

class ActivityGrid(wx.grid.Grid):
    def __init__(self, parent, db):
        wx.grid.Grid.__init__(self, parent, -1)
        self.parent = parent
        table = ActivityTable(db, self, onlySinceEmpty=True)
        self.SetTable(table, True)
        self.EnableEditing(False)
        self.SetRowLabelSize(40)
        self.SetMargins(0,0)
        self.EnableDragRowSize(False)
        self.Unbind(wx.EVT_TEXT) # no effect?
        self.Unbind(wx.EVT_KEY_DOWN)

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

        self.grid = ActivityGrid(self, db)
#        self.grid.Enable(False) # works for disabling input, but makes it gray

        self.bibField = BibTextCtrl(self, recordFn=self.RecordBib)

        boxSizer = wx.BoxSizer(wx.VERTICAL)
        boxSizer.Add(self.grid, 100, wx.EXPAND)
        innerSizer = wx.BoxSizer(wx.HORIZONTAL)
        innerSizer.Add(wx.StaticText(self, wx.ALIGN_LEFT,
                                     "  Record bib after finish: "))
        innerSizer.Add(self.bibField, 0, wx.EXPAND)
        boxSizer.Add(innerSizer, 0, wx.EXPAND)
        self.SetSizer(boxSizer)

        self.hearer = notify.Hear(self)
        self.Bind(notify.EVT_UPDATE_INFO, self.OnHeardNotify)

        self.Show(True)
        self.bibField.SetFocus()

    def __del__(self):
        self.hearer.keepGoing = False

    def RecordBib(self, bibNumber):
        if not None is bibNumber and len(bibNumber) > 0:
            if bibNumber == str(db.Db.FLAG_CORRAL_EMPTY):
                self.db.RecordMatches(self.grid.GetTable().data)
            self.db.RecordBib(bibNumber)
            self.Refresh()

    def Refresh(self):
        self.grid.Reload()

    def OnHeardNotify(self, evt):
        print "Heard msg:%s mine:" % evt.message, evt.likelyFromMe
        if not evt.likelyFromMe:
            self.Refresh()

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
