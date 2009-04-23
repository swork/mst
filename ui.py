#! /usr/local/bin/python

import wx
import wx.grid

class MatchupTable(wx.grid.PyGridTableBase):
    def __init__(self, log):
        wx.grid.PyGridTableBase.__init__(self)
        self.rows = 400
        self.cols = 2
        self.colLabels = ['Bib:ScanTime',
                          'ImpulseTime']
        self.dataTypes = [wx.grid.GRID_VALUE_STRING,
                          wx.grid.GRID_VALUE_STRING,
                          ]
    def GetNumberRows(self):
        return self.rows
    def GetNumberCols(self):
        return self.cols
    def IsEmptyCell(self,row,col):
        return False
    def GetValue(self,row,col):
        return "%d,%d" % (row, col)
    def SetValue(self,row,col,value):
        return True
    def GetColLabelValue(self, col):
        return self.colLabels[col]

class MatchupGrid(wx.grid.Grid):
    def __init__(self, parent, log):
        wx.grid.Grid.__init__(self, parent, -1)
        table = MatchupTable(log)
        self.SetTable(table, True)
        # self.EnableEditing(False)
        self.SetRowLabelSize(0)
        self.SetMargins(0,0)
        self.AutoSizeColumns(False)

class MainFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, size=(300,600))
        self.control = MatchupGrid(self, 2)
        self.Show(True)

app = wx.PySimpleApp()
frame = MainFrame(None, wx.ID_ANY, 'Editor')
app.MainLoop()
