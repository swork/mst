import wx.grid
import weakref
from db import Db, DatetimeAsTimestring

trace = True

class ActivityTable(wx.grid.PyGridTableBase):
    def __init__(self, db, grid, onlySinceEmpty=False):
        if trace: print "activitytable::init"
        wx.grid.PyGridTableBase.__init__(self)
        self.gridRef = weakref.ref(grid)
        self.db = db
        self.onlySinceEmpty = onlySinceEmpty
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
        self.displayMappers = {}
        self.displayMappers['impulsetime']= lambda x: DatetimeAsTimestring(x)

    def Reload(self):
        if trace: print "reload"
        if self.onlySinceEmpty:
            self.data = self.db.GetImpulseActivityTableSinceEmpty()
        else:
            self.data = self.db.GetRecentImpulseActivityTable(self.WantNumberRows())
        self.attrcache = {}
        if trace: print self.data
        self.ResetView()

    def GetGrid(self):
        return self.gridRef()

    def GetNumberRows(self):
        if trace: print "getnumberrows: %d" % len(self.data)
        return len(self.data)

    def WantNumberRows(self):
        if (len(self.data)):
            if trace: print "wantnumberrows: gridsize:%s" % str(self.GetGrid().GetSize())
            return ((self.GetGrid().GetSize()[1] / self.GetGrid().GetRowSize(0))
                    - 1)
        return 50

    def GetNumberCols(self):
        return 3

    def IsEmptyCell(self,row,col):
        return self.data[row][col] is None

    def GetColLabelValue(self, col):
        return self.colLabels[col]

    def GetRowLabelValue(self, row):
        return self.data[row]['impulseid']

    def GetValue(self, row, col):
        if row >= len(self.data):
            return ""
        col_value_name = self.colMap[col]
        value = self.data[row][col_value_name]
        formatted = None
        if not None is value:
            col_display_mapper = lambda x: x
            if self.displayMappers.has_key(col_value_name):
                col_display_mapper = self.displayMappers[col_value_name]
            formatted = col_display_mapper(value)
        if formatted is None:
            return ""
        else:
            return formatted

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

    def EraseImpulse(self, row):
        """Mark impulse record as erased"""
        if not None is self.data[row]['bib']:
            alert()
        else:
            self.db.EraseImpulseByID(self.data[row]['impulseid'])
            self.Reload()
