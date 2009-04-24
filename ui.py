#! /usr/local/bin/python

import wx
import wx.grid
from db import Db
import weakref

trace = False

def alert():
    wx.Sound.PlaySound("alert.wav", wx.SOUND_ASYNC)

class MatchupTable(wx.grid.PyGridTableBase):
    def __init__(self, log, db, grid):
        wx.grid.PyGridTableBase.__init__(self)
        self.gridRef = weakref.ref(grid)
        self.db = db
        (self.data,
         self.impulseCount, 
         self.bibscanCount,
         self.bibscanUnmatchedCount) = db.GetMatchTable()
        self.currentRows = self.GetNumberRows()
        self.colLabels = [
                          'ImpulseTime',
                          'Bib',
                          'Scantime']
        self.colMap = ('impulsetime', 'bib', 'scantime')
        self.dataTypes = [wx.grid.GRID_VALUE_STRING,
                          wx.grid.GRID_VALUE_NUMBER,
                          wx.grid.GRID_VALUE_STRING,
                          ]

    def GetGrid(self):
        return self.gridRef()
    def GetNumberRows(self):
        return len(self.data)
    def GetNumberCols(self):
        return 3
    def IsEmptyCell(self,row,col):
        return self.data[row][self.colMap[col]] is None
    def GetColLabelValue(self, col):
        return self.colLabels[col]

    def ResetView(self):
        """Trim/extend the control's rows and update all values"""
        self.GetGrid().BeginBatch()
        for current, new, delmsg, addmsg in [
            (self.currentRows, self.GetNumberRows(), wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED),
#            (self.currentColumns, self.GetNumberCols(), wx.grid.GRIDTABLE_NOTIFY_COLS_DELETED, wx.grid.GRIDTABLE_NOTIFY_COLS_APPENDED),
            ]:
            if new < current:
                if trace: print "msg Del: current %d, new %d" % (current, new)
                msg = wx.grid.GridTableMessage(
                    self,
                    delmsg,
                    new,    # position
                    current-new,
                    )
                self.GetGrid().ProcessTableMessage(msg)
                self.currentRows = new
            elif new > current:
                msg = wx.grid.GridTableMessage(
                    self,
                    addmsg,
                    new-current
                    )
                self.GetGrid().ProcessTableMessage(msg)
                self.currentCols = new
        self.UpdateValues()
        self.GetGrid().UpdateStatusBar()
        self.GetGrid().EndBatch()
 
        # The scroll bars aren't resized (at least on windows)
        # Jiggling the size of the window rescales the scrollbars
        if False:
            h,w = grid.GetSize()
            grid.SetSize((h+1, w))
            grid.SetSize((h, w))
            grid.ForceRefresh()
 
    def UpdateValues( self ):
        """Update all displayed values"""
        msg = wx.grid.GridTableMessage(self,
                                    wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.GetGrid().ProcessTableMessage(msg)

    def GetAttr(self, row, col, huh):
        if self.data[row]['bib'] == Db.FLAG_CORRAL_EMPTY:
            attr = wx.grid.GridCellAttr()
            attr.SetBackgroundColour("light gray")
            return attr
        if (not self.data[row]['impulseid'] is None and
            not self.data[row]['scanid'] is None):
            attr = wx.grid.GridCellAttr()
            attr.SetBackgroundColour("pale green")
            return attr
        return None

    def GetValue(self,row,col):
        data = self.data[row][self.colMap[col]]
        if data is None:
            return ""
        else:
            return data

    def AssociateScanWithImpulseByRows(self, top, bot):
        """Mark a finish impulse as belonging to a particular bib."""
        assert not None is self.data[bot]['scanid']
        if self.data[top]['impulsetime'] is None:
            alert()
            if not None is self.data[top]['impulseid']:
                inconsistency()
        elif not None is self.data[bot]['impulsetime']:
            alert()
            if self.data[bot]['impulseid'] is None:
                inconsistency()
        elif not None is self.data[top]['bib']:
            alert()
            if self.data[top]['bib'] is None:
                inconsistency()
        elif self.data[bot]['bib'] is None:
            alert()
            if not None is self.data[bot]['bib']:
                inconsistency()
        elif self.data[bot]['bib'] == Db.FLAG_CORRAL_EMPTY:
            alert()
        elif self.data[bot]['bib'] == Db.FLAG_ERROR:
            alert()
        else:
            self.db.AssignImpulseToScanByIDs(self.data, top, bot)
            self.bibscanUnmatchedCount -= 1
            self.ResetView()

    def GetStatusBarText(self):
        return "%d impulses, %d bibs, %d unassigned" % (self.impulseCount,
                                                    self.bibscanCount,
                                                    self.bibscanUnmatchedCount)

class MatchupGrid(wx.grid.Grid):
    def __init__(self, parent, log, db):
        wx.grid.Grid.__init__(self, parent, -1)
        self.parent = parent
        table = MatchupTable(log, db, self)
        self.SetTable(table, True)
        # self.EnableEditing(False)
        self.SetRowLabelSize(40)
        self.SetMargins(0,0)
        self.AutoSizeColumns(False)

        # Cheesy way to associate bib scan with impulse: drag a range of rows
        wx.grid.EVT_GRID_RANGE_SELECT(self, self.OnRangeSelect)

    def OnRangeSelect(self, evt):
        if evt.Selecting():
            top = evt.GetTopRow()
            bot = evt.GetBottomRow()
            if trace: print "OnRangeSelect: top %d, bottom %d" % (top, bot)
            self.GetTable().AssociateScanWithImpulseByRows(top, bot)

    def UpdateStatusBar(self):
        self.parent.UpdateStatusBar()

    def GetStatusBarText(self):
        return self.GetTable().GetStatusBarText()

class MainFrame(wx.Frame):
    def __init__(self, parent, id, title, db):
        wx.Frame.__init__(self, parent, id, title, size=(300,600))
        self.control = MatchupGrid(self, 2, db)

        self.CreateStatusBar()
        self.UpdateStatusBar()

        menuBar = wx.MenuBar(wx.MB_DOCKABLE)
        fileMenu = wx.Menu()
        fileMenu.Append(wx.ID_SAVE, "&Save and refresh\tCtrl-S", "Commit pending changes")

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
        self.Bind(wx.EVT_MENU, self.OnSave, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self.OnQuit, id=wx.ID_EXIT)

        self.Show(True)

    def OnAbout(self, evt):
        dlg = wx.MessageDialog(self, "Edit timing results", "About", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnSave(self, evt):
        dlg = wx.MessageDialog(self, "Not implemented",
                               "Save", wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()

    def OnQuit(self, evt):
        dirty = False
        if dirty:
            dlg = wx.MessageDialog(self, u"Unsaved changes. Save before exit?",
                                   "Save",
                                   wx.YES_NO |
                                   wx.YES_DEFAULT | 
                                   wx.ICON_QUESTION)
            print dlg.ShowModal()
            dlg.Destroy()
        self.Close(True)

    def UpdateStatusBar(self):
        self.SetStatusText(self.control.GetStatusBarText())

class MSTEditorApp(wx.PySimpleApp):
    pass 

if __name__ == "__main__":
    db = Db('sqlite:///:memory:', echo=False)
    db.LoadTestData()
    db.session.commit()

#    set = { "impulse": 2 }
#    db.session.query(Db.Scan).filter("bib = 101").update(set)
#    db.session.commit()

    app = MSTEditorApp()
    frame = MainFrame(None, wx.ID_ANY, 'Editor', db)
    app.MainLoop()

