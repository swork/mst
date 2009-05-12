#! /usr/local/bin/python

import wx
import wx.grid
from db import Db
import weakref
import re

trace = True

def alert():
    wx.Sound.PlaySound("alert.wav", wx.SOUND_ASYNC)

class MatchupTable(wx.grid.PyGridTableBase):
    def __init__(self, log, db, grid):
        wx.grid.PyGridTableBase.__init__(self)
        self.gridRef = weakref.ref(grid)
        self.db = db
        self.data = []
        self.impulseCount = 0
        self.bibscanCount = 0
        self.bibscanUnmatchedCount = 0
        self.currentRows = 0
        self.colLabels = [
                          'ImpulseTime',
                          'Bib',
                          'Scantime']
        self.colMap = ('impulsetime', 'bib', 'scantime')
        self.dataTypes = [wx.grid.GRID_VALUE_STRING,
                          wx.grid.GRID_VALUE_NUMBER,
                          wx.grid.GRID_VALUE_STRING,
                          ]
        self.timere = re.compile("\d\d:\d\d:\d\d.\d+")

    def Reload(self):
        if trace: print "Reload..."
        (self.data,
         self.impulseCount, 
         self.bibscanCount,
         self.bibscanUnmatchedCount) = self.db.GetMatchTable()
        self.ResetView()

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

        resize_columns = False
        if self.currentRows is 0:
            resize_columns = True

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
        if resize_columns:
            self.GetGrid().ResizeColumns(and_outer = True)
            
        self.GetGrid().UpdateStatusBar()
        self.GetGrid().EndBatch()
 
    def UpdateValues( self ):
        """Update all displayed values"""
        msg = wx.grid.GridTableMessage(self,
                                    wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.GetGrid().ProcessTableMessage(msg)

    def GetAttr(self, row, col, huh):
#        if trace: print "GetAttr(self, row=%d, col=%d, huh=%s); rows=%d" % (row, col, repr(huh), len(self.data))
        if self.data[row]['bib'] == Db.FLAG_CORRAL_EMPTY:
            attr = wx.grid.GridCellAttr()
            attr.SetBackgroundColour("light gray")
            return attr
        if self.data[row]['bib'] == Db.FLAG_ERROR:
            attr = wx.grid.GridCellAttr()
            attr.SetBackgroundColour("yellow")
            return attr
        if (not None is self.data[row]['impulseid'] and
            not None is self.data[row]['scanid']):
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
        if trace: print "ASWIR(top=%d, bot=%d): tbib=%s, bbib=%s" % (top, bot, self.data[top]['bib'], self.data[bot]['bib'])
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
        return "%d impulses, %d bib scans, %d unassigned" % (self.impulseCount,
                                                    self.bibscanCount,
                                                    self.bibscanUnmatchedCount)

    def SaveNewValue(self, row, col, str):
        """Validate and save value; return value or None on failure."""
        if (col == 0):
            print "ImpulseTime, %d,%d (%s)" % (row, col, str)
            if not None is self.data[row]['scanid']:
                alert()
            elif self.timere.match(str):
                return self.SetCellValue(row, col, str)
        elif (col == 1):
            print "Bib"
        elif (col == 2):
            print "ScanTime"
        else:
            print "Huh?"
        return None

class MatchupGrid(wx.grid.Grid):
    def __init__(self, parent, log, db):
        wx.grid.Grid.__init__(self, parent, -1)
        self.parent = parent
        table = MatchupTable(log, db, self)
        self.SetTable(table, True)
        # self.EnableEditing(False)
        self.SetRowLabelSize(40)
        self.SetMargins(0,0)
        self.EnableDragRowSize(False)

        wx.grid.EVT_GRID_RANGE_SELECT(self, self.OnRangeSelect)
        wx.grid.EVT_GRID_CELL_CHANGE(self, self.OnGridCellChange)
        wx.grid.EVT_GRID_CELL_LEFT_CLICK(self,self.OnGridLeftClick)
        wx.grid.EVT_GRID_CELL_LEFT_DCLICK(self,self.OnGridLeftDClick)
        wx.grid.EVT_GRID_CELL_RIGHT_CLICK(self,self.OnGridRightClick)
#        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)

    def ResizeColumns(self, and_outer = False):
        self.AutoSizeColumns(False)
        if and_outer:
            self.parent.ResetWidth()

    def GetColumnWidthsSum(self):
        n = self.GetNumberCols()
        width = self.GetRowLabelSize() + 1 # include border, ugh
        for i in range(0,n):
            w = self.GetColSize(i) + 1
            width += w
            print "width col %d is %d" % (i, w)
        return width + 1
        
    def UpdateStatusBar(self):
        self.parent.UpdateStatusBar()

    def GetStatusBarText(self):
        return self.GetTable().GetStatusBarText()

    def OnRangeSelect(self, evt):
        if evt.Selecting():
            top = evt.GetTopRow()
            bot = evt.GetBottomRow()
            if trace: print "OnRangeSelect: top %d, bottom %d" % (top, bot)
            self.GetTable().AssociateScanWithImpulseByRows(top, bot)
            self.ClearSelection()

    def OnGridCellChange(self, evt):
        if trace: print("OnGridCellChange: (%d,%d)\n" %
                        (evt.GetRow(), evt.GetCol()))
        if self.GetTable().SaveNewValue(evt.GetRow(), evt.GetCol(),
                                        evt.GetString()) is None:
            alert()

    def OnGridLeftClick(self, evt):
        print "click %d,%d" % (evt.GetRow(), evt.GetCol())
        evt.Skip()

    def OnGridLeftDClick(self, evt):
        print "dclick %d,%d" % (evt.GetRow(), evt.GetCol())

    def OnGridRightClick(self, evt):
        print "right click %d,%d" % (evt.GetRow(), evt.GetCol())
        self.SetGridCursor(evt.GetRow(), evt.GetCol())

        # only bind events once; could have done this way up top.
        if not hasattr(self, "ctxInsertBefore"):
            self.ctxInsertBefore = wx.NewId()
            self.ctxInsertAfter = wx.NewId()
            self.ctxInsertBib = wx.NewId()
            self.ctxDeleteThis = wx.NewId()
            self.ctxDisassociateThis = wx.NewId()

            self.Bind(wx.EVT_MENU, self.OnCtxInsertBefore,
                      id=self.ctxInsertBefore)
            self.Bind(wx.EVT_MENU, self.OnCtxInsertAfter, 
                      id=self.ctxInsertAfter)
            self.Bind(wx.EVT_MENU, self.OnCtxInsertBib, 
                      id=self.ctxInsertBib)
            self.Bind(wx.EVT_MENU, self.OnCtxDeleteThis,
                      id=self.ctxDeleteThis)
            self.Bind(wx.EVT_MENU, self.OnCtxDisassociateThis,
                      id=self.ctxDisassociateThis)

        menu = wx.Menu()
        item = wx.MenuItem(menu, self.ctxInsertBefore, "Insert Impulse Before")
#        bmp = images.Smiles.GetBitmap()
#        item.SetBitmap(bmp)
        menu.AppendItem(item)
        item = wx.MenuItem(menu, self.ctxInsertAfter, "Insert Impulse After")
        menu.AppendItem(item)
        item = wx.MenuItem(menu, self.ctxInsertBib, "Insert Bib Scan")
        menu.AppendItem(item)
        item = wx.MenuItem(menu, self.ctxDeleteThis, "Delete Bib Scan")
        item.Enable(False)
        menu.AppendItem(item)
        item = wx.MenuItem(menu, self.ctxDisassociateThis, "Disassociate Bib from Impulse")
        menu.AppendItem(item)

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        self.PopupMenu(menu)
        menu.Destroy()

    def OnCtxInsertAfter(self, evt):
        pass
    def OnCtxInsertBefore(self, evt):
        pass
    def OnCtxInsertBib(self, evt):
        pass
    def OnCtxDeleteThis(self, evt):
        pass
    def OnCtxDisassociateThis(self, evt):
        pass

class MainFrame(wx.Frame):
    ID_EASY = 43
    def __init__(self, parent, id, title, db):
        wx.Frame.__init__(self, parent, id, title, size=(299,600))
        self.db = db
        self.control = MatchupGrid(self, 2, db)

        self.CreateStatusBar()
        self.UpdateStatusBar()

        menuBar = wx.MenuBar(wx.MB_DOCKABLE)
        fileMenu = wx.Menu()
        fileMenu.Append(wx.ID_SAVE, "&Save and refresh\tCtrl-S", "Commit pending changes")

        editMenu = wx.Menu()
        editMenu.Append(wx.ID_UNDO, "&Undo\tCtrl-Z", "Not yet implemented")
        editMenu.Append(wx.ID_REDO, "Redo\tShift-Ctrl-Z", "Not yet implemented")
        editMenu.AppendSeparator()
        editMenu.Append(MainFrame.ID_EASY, "Make Easy Assignments",
                        "Assign finishes to obviously corresponding scans")

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
        dlg = wx.MessageDialog(self, "Edit Timing", "About", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def OnSave(self, evt):
        self.db.session.commit()
        self.control.GetTable().Reload()

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

    def ResetWidth(self):
        gridwidth = self.control.GetColumnWidthsSum()
        print gridwidth
        framesize = self.GetClientSize()
        newsize = (gridwidth + 15, framesize[1]) # scroll bar width
        print "newsize: ", newsize
        self.SetClientSize(newsize)
        size = self.GetSize()
        self.SetMinSize((size[0], 100))
        self.SetMaxSize((size[0], 10000))

if __name__ == "__main__":
    db = Db('sqlite:///:memory:', echo=False)
    db.LoadTestData()
    db.session.commit()

#    set = { "impulse": 2 }
#    db.session.query(Db.Scan).filter("bib = 101").update(set)
#    db.session.commit()

    app = MSTEditorApp()
    app.MainLoop()

