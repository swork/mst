#! /usr/local/bin/python

import wx
import wx.grid
from db import Db
import weakref
import re

trace = True

def alert():
    wx.Sound.PlaySound("alert.wav", wx.SOUND_ASYNC)

class ActivityTable(wx.grid.PyGridTableBase):
    def __init__(self, db, grid):
        if trace: print "activitytable::init"
        wx.grid.PyGridTableBase.__init__(self)
        self.gridRef = weakref.ref(grid)
        self.db = db
        self.data = []
        self.currentRows = 0
        self.colLabels = [
                          'ImpulseTime',
                          'Bib',
                          'Competitor']
        self.colMap = ('impulsetime', 'bib', 'competitor')
        self.dataTypes = [wx.grid.GRID_VALUE_STRING,
                          wx.grid.GRID_VALUE_NUMBER,
                          wx.grid.GRID_VALUE_STRING,
                          ]

    def Reload(self):
        if trace: print "reload"
        self.data = self.db.GetRecentImpulseActivityTable(self.WantNumberRows())
        self.ResetView()

    def GetGrid(self):
        return self.gridRef()

    def GetNumberRows(self):
        if trace: print "getnumberrows: %d" % len(self.data)
        return len(self.data)

    def WantNumberRows(self):
        if (len(self.data)):
            if trace: print "wantnumberrows: gridsize:%s" % str(self.GetGrid().GetSize())
            return ((self.GetGrid().GetSize()[1]
                     / self.GetGrid().GetRowSize(0))
                    - 1)
        return 50

    def GetNumberCols(self):
        return 3

    def IsEmptyCell(self,row,col):
        return self.data[row][self.colMap[col]] is None

    def GetColLabelValue(self, col):
        return self.colLabels[col]

    def GetRowLabelValue(self, row):
        return self.data[row]['impulseid']

    def GetValue(self, row, col):
        if row >= len(self.data):
            return ""
        data = self.data[row][self.colMap[col]]
        if data is None:
            return ""
        else:
            return data

    def ResetView(self):
        """Trim/extend the control's rows and update all values"""
        self.GetGrid().BeginBatch()

#         resize_columns = False
#         if self.currentRows is 0:
#             resize_columns = True

        if len(self.data) < self.currentRows:
            msg = wx.grid.GridTableMessage(self,
                                         wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED,
                                           0, # len(self.data),
                                           self.currentRows - len(self.data))
            self.GetGrid().ProcessTableMessage(msg)
        elif len(self.data) > self.currentRows:
            msg = wx.grid.GridTableMessage(self,
                                         wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED,
                                           len(self.data) - self.currentRows)
            self.GetGrid().ProcessTableMessage(msg)
        self.currentRows = len(self.data)
        self.UpdateValues()
        self.GetGrid().AutoSizeColumns(False)
#        if resize_columns:
#            self.GetGrid().ResizeColumns(and_outer = True)
            
#        self.GetGrid().UpdateStatusBar()
        self.GetGrid().EndBatch()
 
    def UpdateValues( self ):
        """Update all displayed values"""
        msg = wx.grid.GridTableMessage(self,
                                    wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.GetGrid().ProcessTableMessage(msg)

class ActivityGrid(wx.grid.Grid):
    def __init__(self, parent, db):
        wx.grid.Grid.__init__(self, parent, -1)
        self.parent = parent
        table = ActivityTable(db, self)
        self.SetTable(table, True)
        self.EnableEditing(False)
        self.SetRowLabelSize(40)
        self.SetMargins(0,0)
        self.EnableDragRowSize(False)
        wx.grid.EVT_GRID_CELL_LEFT_CLICK(self, self.OnGridCellClick)

    def OnGridCellClick(self, evt):
        parent.RecordImpulse()

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

        self.grid = ActivityGrid(self, db)
        #grid.WriteText(u"Hello again!\nAnd how are you?\n")

        reportButton = wx.Button(self)
        reportButton.SetDefault()
        reportButton.SetLabel("Click Here to record a finish impulse")
        self.Bind(wx.EVT_BUTTON, self.RecordImpulse)

        boxSizer = wx.BoxSizer(wx.VERTICAL)
        boxSizer.Add(self.grid, 100, wx.EXPAND)
        boxSizer.Add(reportButton, 0, wx.EXPAND)
        self.SetSizer(boxSizer)

        self.Show(True)

    def RecordImpulse(self, id):
        self.db.RecordImpulse()
        self.click_counter += 1
        self.SetStatusText("Click %d" % self.click_counter)
        self.Refresh()

    def Refresh(self):
        self.grid.Reload()

    def OnAbout(self, evt):
        dlg = wx.MessageDialog(self, "Record Finish Impulses", "About", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnQuit(self, evt):
        dlg = wx.MessageDialog(self, u"Quit: Are you sure?",
                                   "Quit",
                                   wx.YES_NO |
                                   wx.NO_DEFAULT | 
                                   wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            dlg.Destroy()
            self.Close(True)

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

