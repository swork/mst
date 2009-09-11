from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, relation, backref, join
from sqlalchemy.databases import mysql
from sqlalchemy import sql
from datetime import datetime
import types, re
from copy import copy
import notify
import os

import mapfinish

trace = False
Base = declarative_base()
CONNECTION_SPECIFIER = 'NO_DEFAULT'
LOGFILE = 'no/default/at/all'
REPORT_TITLE = "DEFAULT REPORT TITLE - CHECK .mst.XXX"
AUTO_ASSIGN_SCANS = False
ENTRIES_FINISH_CATEGORIES = ('cat','agegp','bike','ath_clyde','gender','reside')
RESTRICTED_REPORT_LIST = ((), ('cat',), ('cat','agegp'), ('cat','ath_clyde'),
                          ('cat','reside'), ('reside',), ('cat','bike'),
                          ('bike',))
REPORT_CATEGORIES_LIMIT = 15

timere = re.compile(r"(\d+):(\d+):(\d+).?(\d*)")
def ConvertToDatetime(timeValue):
    val = datetime.now()
    t = type(timeValue)
    if t == types.StringType:
        res = timere.match(timeValue)
        ms = 0
        if (res.group(4) != ''):
            ms_order = len(res.group(4))
            ms_raw = int(res.group(4))
            ms = ms_raw * (10 ** (6 - ms_order))
        return val.replace(hour=int(res.group(1)), minute=int(res.group(2)),
                           second=int(res.group(3)), microsecond=ms,
                           tzinfo=None)
    if t == types.DateTimeType:
        return timeValue.replace(tzinfo=None)
    raise "TimeValueConvert got input type %s, can't figure it out..." % t

def DatetimeAsTimestring(dt):
    return dt.strftime("%H:%M:%S.%f")

def IsFlagValue(bibnumber):
    if bibnumber is None:
        return False
    if (bibnumber == Db.FLAG_CORRAL_EMPTY
        or bibnumber == Db.FLAG_ERROR
        or bibnumber == Db.FLAG_DONT_ASSIGN):
        return True
    return False

class RowProxy(object):
    """An "ordered dictionary" to emulate SQLAlchemy's RowProxy object."""
    def __init__(self, arr):
        self.arr = arr
        self.dict = {}
        for i in range(0, len(arr), 2):
            self.dict[arr[i]] = arr[i+1]
    def __repr__(self):
        return "<Db.RowProxy: %s>" % self.arr.__repr__()
    def __getattr__(self, key):
        if key in self.dict:
            return self.dict[key]
        return self.getattr(key)
    def __getitem__(self, i):
        try:
            return self.arr[i*2+1]
        except TypeError:
            try:
                return self.dict[i]
            except:
                raise
    def __setitem__(self, key, value):
        try:
            self.arr[key*2+1] = value
        except TypeError:
            try:
                if key in self.dict:
                    self.dict[key] = value
                else:
                    raise AttributeError, key
            except:
                raise
    def append(self, key, value):
        self.arr.append(key)
        self.arr.append(value)
        self.dict[key] = value
    def Values(self):
        return self.arr[1::2]
    def SubsetColumns(self, keys):
        res = RowProxy([])
        for k in keys:
            res.append(k, self.dict[k])
        return res

def multiListSliceCount(lol):
    """Determine the terminating index for multiListSlice"""
    count = 1
    for i in range(0, len(lol)):
        count *= len(lol[i])
    #print "multiListSliceCount of:%s is:%d" % (lol, count)
    return count

def multiListSlice(lol, index):
    """Pick a single element from each list in a list of lists and return
    the set as a list."""
    divisor = 1
    values = []
    for i in range(0, len(lol)):
        index = (index / divisor) % len(lol[i])
        values[i] = lol[i][index]
        divisor *= len(lol[i])
    return values

def flatten(x):
    result = []
    for el in x:
        if hasattr(el, "__iter__") and not isinstance(el, basestring):
            result.extend(flatten(el))
        else:
            result.append(el)
    return result

def hamming_weight(n):
    count = 0
    while n:
        n = n & (n-1)           # zero the rightmost bit
        count += 1
    return count

def orderByIncreasingBitCount(n):
    """Return an ordering of the n-bit integers by increasing bit count."""
    res = [0]                   # freebie
    biggest = 2**n - 1
    for i in range(1, n):
        for j in range(1, biggest):
            if hamming_weight(j) == i:
                res.append(j)
    res.append(biggest)         # another freebie
    return res

class QueryGeneratorTop(object):
    def __init__(self, dbobject, table, columnNames):
        self.db = dbobject
        self.table = table
        self.columnNames = columnNames
        self.zeros = {}         # dict of tuple=>1 colval combos
        self.distinctValues = RowProxy([])
        mapping = mapfinish.MapFinish()
        for k in columnNames:
            sql= ("select distinct %s from %s where %s is not NULL and %s != '' order by %s"
                  % (k, table, k, k, k))
            listOfTuples = flatten(self.db.engine.execute(sql).fetchall())
            self.distinctValues.append(k, mapping.Map(k, listOfTuples))

    def __repr__(self):
        return ("<QueryGeneratorTop: table:%s columnNames:%s distinctValues:%s"
                % (self.table, self.columnNames, self.distinctValues))

class QueryGenerator(object):
    def __init__(self, qgt, column_subset_mask, formatter):
        self.top = qgt
        self.formatter = formatter
        self.counter = 0
        self.columnNames = []
        self.alls = []          # columns excluded => "all values"

        # Pick columns from full list by bits set in subset_mask
        for i in range(0, len(self.top.columnNames)):
            if ((1 << i) & column_subset_mask) != 0:
                self.columnNames.append(self.top.columnNames[i])
            else:
                self.alls.append(self.top.columnNames[i])
        if len(self.columnNames) == 0:
            self.distincts = RowProxy([]) # empty
            self.limit = 1
        else:
            self.distincts = self.top.distinctValues.SubsetColumns(self.columnNames)
            self.limit = multiListSliceCount(self.distincts.Values())

    def __repr__(self):
        return ("<QueryGenerator: counter:%d columnNames:%s alls:%s"
                + " distincts:%s limit:%d>") \
            % (self.counter, self.columnNames, self.alls, self.distincts, 
               self.limit)

    def nextSelections(self):
        if self.counter >= self.limit:
            return None
        divisor = 1
        selections = {}
        for i in range(0, len(self.columnNames)):
            distinct_column_values = self.distincts.Values()[i]
            index = (self.counter / divisor) % len(distinct_column_values)
            name = self.columnNames[i]
            value = distinct_column_values[index]
            selections[name] = value
            divisor *= len(distinct_column_values)
        self.counter += 1
        return selections

    def _whereClause(self, selections):
        keys = selections.keys()
        if len(keys):
            items = " and ".join(map(lambda k: "%s = '%s'" % (k, selections[k]),
                                     keys))
            return "where %s" % items
        return ""

    def _generateResultCombinations_getRows(self, selections):
        whereClause = self._whereClause(selections)
        sql = "select * from %s %s order by totalsecs limit %d" \
            % (self.top.table, whereClause, REPORT_CATEGORIES_LIMIT)
        rows = self.top.db.engine.execute(sql).fetchall()
        sql = "select count(*) from %s %s" \
            % (self.top.table, whereClause)
        count = self.top.db.engine.execute(sql).fetchone()[0]
        return rows, count

    def IsInZeros(self, selections):
        keys = selections.keys()
        for i in range(0,len(keys)):
            for j in range(i,len(keys)):
                tester = {}
                for k in keys[i:j+1]:
                    tester[k] = selections[k]
                trykey = tuple(sorted(tester.items()))
                #print "IsInZeros testing i:%d j:%d got:%s in:%s" % (i, j, trykey, self.top.zeros)
                if tuple(sorted(tester.items())) in self.top.zeros:
                    #print "IsInZeros %s got True" % selections
                    return True
        #print "IsInZeros %s got False" % selections
        return False

    def GenerateResultCombinations(self):
        selections = self.nextSelections()
        while not None is selections:
            if self.IsInZeros(selections) is False:
                rows,count= self._generateResultCombinations_getRows(selections)
                if count > 0:
                    self.formatter(selections, rows, count)
                else:
                    adder = tuple(sorted(selections.items()))
                    self.top.zeros[adder] = 0
                    #print "Adding:%s to zeros, now:%s" % (adder, self.top.zeros)
            selections = self.nextSelections()

class Db(object):
    """Hold the database session info.  Only one instance possible?"""

    # Special "bib" numbers
    FLAG_CORRAL_EMPTY = 999
    FLAG_ERROR = 998
    FLAG_DONT_ASSIGN = 0

    def __init__(self, echo):
        self.engine = create_engine(CONNECTION_SPECIFIER, echo=echo)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        Base.metadata.create_all(self.engine)
        self.notifier = notify.Say()

    def WriteLog(self, sql_command):
        fname = os.path.expanduser(LOGFILE % os.getpid())
        open(fname, 'a').write("%s;\n" % sql_command)

    class Group(Base):
        """Start time by category"""
        __tablename__ = 'groups'

        id = Column(Integer(11), primary_key=True)
        startkey = Column(String(40), nullable=False) # same len as entry.cat
        starttod = Column(mysql.MSDateTime, nullable=True, default=None)

        def __init__(self, group, starttod):
            self.group = group
            self.starttod = starttod

        def __repr__(self):
            return "<Db.Entry(%d,'%s','%s')>" % (self.id,
                                                  self.group, self.starttod)

    class Entry(Base):
        """Registration info for an entrant"""
        __tablename__ = 'entries'

        id = Column(Integer(11), primary_key=True)
        bib = Column(Integer(11), nullable=False)
        lastname = Column(String(40), nullable=False)
        firstname = Column(String(40), nullable=False)
        cat = Column(String(40), nullable=False)
        agegp = Column(String(10), nullable = True, default=None)
        bike = Column(String(10), nullable = True, default=None)
        ath_clyde = Column(String(1), nullable=True, default=None)
        gender = Column(String(1), nullable=True, default=None)
        reside = Column(String(7), nullable=True, default=None)
        starttod = Column(mysql.MSDateTime, nullable=True, default=None)
        finishtod = Column(mysql.MSDateTime, nullable=True, default=None)
        ms = Column(Integer(7), nullable=True, default=None)
        totalsecs = Column(Integer(11), nullable=True, default=None)
        dnf = Column(Integer(1), nullable=True, default=None)

        def __init__(self, bib, firstname):
            self.bib = bib
            self.firstname = firstname

        def __repr__(self):
            return "<Db.Entry(%d,'%s','%s')>" % (self.id, 
                                                 self.firstname, self.bib)

    class Impulse(Base):
        """Time at which *someone* crossed the finish line. Assign bib later"""
        __tablename__ = 'impulses'

        id = Column(Integer(11), primary_key=True)
        impulsetime = Column(mysql.MSDateTime, nullable=False)
        ms = Column(Integer(7), nullable=False)
        erased = Column(mysql.MSDateTime, nullable=True, default=None)

        def __init__(self, impulsetime):
            if type(impulsetime) != datetime:
                dt = ConvertToDatetime(impulsetime)
            else:
                dt = impulsetime
            self.impulsetime = dt
            self.ms = dt.microsecond

        def __repr__(self):
            return "<Db.Impulse(%d,'%s')>" % (self.id, self.impulsetime)

    class Scan(Base):
        """Bib number and time scanned as finisher leaves the finish corral"""
        __tablename__ = 'scans'

        id = Column(Integer(11), primary_key=True)
        scantime = Column(mysql.MSDateTime, nullable=False)
        bib = Column(Integer(11), ForeignKey("entries.bib"), nullable=False)
        impulse = Column(Integer(11), ForeignKey("impulses.id"), nullable=True)

        entry_bib = relation("Entry", backref=backref('scans', order_by=bib))
        impulse_id = relation("Impulse",
                              backref=backref('impulses', order_by=id))

        def __init__(self, scantime, bib):
            if type(scantime) != datetime:
                self.scantime = ConvertToDatetime(scantime)
            else:
                self.scantime = scantime
            self.bib = bib

        def __repr__(self):
            return "<Db.Scan(%d,'%s',%d)>" % (self.id, self.scantime, self.bib)

    def impulseActivityTableSinceEmptyWithError(self, impulses_res, scans_res):
        results = []
        impulses_res.reverse()
        scans_res.reverse()
        #print "in i:%d s:%d" % (len(impulses_res), len(scans_res))
        irow = impulses_res.pop() if len(impulses_res) > 0 else None
        srow = scans_res.pop()    if len(scans_res) > 0    else None
        while True:
            doScan = False
            doImpulse = False
            if srow and irow:
                if srow.scantime > irow.impulsetime:
                    doScan = True
                else:
                    doImpulse = True
            elif srow:
                doScan = True
            elif irow:
                doImpulse = True
            else:
                break
            if doScan:
                results.insert(0, RowProxy(['impulseid', None,
                                            'impulsetime', None,
                                            'bib', srow.bib,
                                            'competitor', srow.competitor,
                                            'scanid', srow.scanid,
                                            'scanimpulse', srow.impulse,
                                            'scantime', srow.scantime]))
                srow = scans_res.pop() if len(scans_res) > 0 else None
            elif doImpulse:
                itime = irow.impulsetime.replace(microsecond=irow.ms)
                results.insert(0, RowProxy(['impulseid', irow.id,
                                            'impulsetime', itime,
                                            'bib', None,
                                            'competitor', None,
                                            'scanid', None,
                                            'scanimpulse', None,
                                            'scantime', None]))
                irow = impulses_res.pop() if len(impulses_res) > 0 else None
            else:
                inconsistent()
        return results

    def GetImpulseActivityTableSinceEmpty(self):
        empty = self.engine.execute("""
            select max(scantime) as lastTime
            from scans
            where bib=%s""" % Db.FLAG_CORRAL_EMPTY).fetchone()

        where_impulse= 'where impulses.erased is NULL and scans.impulse is NULL'
        if not None is empty.lastTime:
            where_impulse += " and impulsetime >= '%s'" % empty.lastTime
        sql = """
            select impulses.id as id,
                   impulses.impulsetime as impulsetime,
                   impulses.ms as ms,
                   scans.impulse as scans_impulse
            from impulses
                left outer join scans on impulses.id = scans.impulse
            %s
            order by impulsetime desc, ms desc, id desc""" % where_impulse
        impulses_res = self.engine.execute(sql).fetchall()
        iorig = copy(impulses_res)
        #print "iorig sql:", sql
        #print "iorig res:", iorig

        where_scan = 'where scans.impulse is NULL'
        if not None is empty.lastTime:
            where_scan += (" and scans.bib != %s and scantime >= '%s'"
                           % (Db.FLAG_CORRAL_EMPTY, empty.lastTime))
        scans_res = self.engine.execute("""
            select scans.id as scanid,
                   scans.bib as bib,
                   scans.scantime as scantime,
                   scans.impulse as impulse,
                   CONCAT(entries.firstname,' ',entries.lastname) as competitor
            from scans
                left outer join entries on scans.bib = entries.bib
            %s
            order by scantime desc""" % where_scan).fetchall()
        sorig = copy(scans_res)

        results = []
        irow = impulses_res.pop() if len(impulses_res) > 0 else None
        srow = scans_res.pop()    if len(scans_res) > 0    else None
        while True:
            if srow and srow.bib == Db.FLAG_ERROR:
                return self.impulseActivityTableSinceEmptyWithError(iorig,sorig)
            doScan = False
            doImpulse = False
            doMatch = False
            if irow and srow:
                diff = srow.scantime - irow.impulsetime
                if (irow.impulsetime < srow.scantime
                    and diff.days == 0 and diff.seconds < 5*60):
                    doMatch = True
                elif srow.scantime < irow.impulsetime:
                    doScan = True
                else:
                    doImpulse = True
            elif irow:
                doImpulse = True
            elif srow:
                doScan = True
            else:
                break;
            if doMatch:
                itime = irow.impulsetime.replace(microsecond=irow.ms)
                results.append(RowProxy(['impulseid', irow.id,
                                         'impulsetime', itime,
                                         'bib', srow.bib,
                                         'competitor', srow.competitor,
                                         'scanid', srow.scanid,
                                         'scanimpulse', srow.impulse,
                                         'scantime', srow.scantime]))
                irow = impulses_res.pop() if len(impulses_res) > 0 else None
                srow = scans_res.pop()    if len(scans_res)    > 0 else None
            elif doScan:
                results.append(RowProxy(['impulseid', None,
                                         'impulsetime', None,
                                         'bib', srow.bib,
                                         'competitor', srow.competitor,
                                         'scanid', srow.scanid,
                                         'scanimpulse', srow.impulse,
                                         'scantime', srow.scantime]))
                srow = scans_res.pop() if len(scans_res) > 0 else None
            elif doImpulse:
                itime = irow.impulsetime.replace(microsecond=irow.ms)
                results.append(RowProxy(['impulseid', irow.id,
                                         'impulsetime', itime,
                                         'bib', None,
                                         'competitor', None,
                                         'scanid', None,
                                         'scanimpulse', None,
                                         'scantime', None]))
                irow = impulses_res.pop() if len(impulses_res) > 0 else None
            else:
                inconsistent()
                break
        return results

    def RecordImpulse(self, impulseTime=None):
        if impulseTime is None:
            impulseTime = datetime.now()
        if trace: print impulseTime
        sql = """ insert into impulses (impulsetime, ms)
                  values ('%s', %d)""" % (impulseTime.isoformat(),
                                          impulseTime.microsecond)
        self.engine.execute(sql)
        self.WriteLog(sql)
        self.notifier.NotifyAll()

    def RecordBib(self, bib):
        if trace: print "recordbib:%d" % bib
        scantime = datetime.now()
        sql = """insert into scans (scantime, bib)
                 values ('%s', %s)""" % (scantime, bib)
        self.engine.execute(sql)
        self.WriteLog(sql)
        self.notifier.NotifyAll()

    def RecordMatches(self, data):
        #print "recordmatches:", data
        for row in data:
            if (row.scanimpulse is None
                and not None is row.scanid
                and not None is row.impulseid):
                sql = """
                    update scans 
                    set impulse = %d
                    where id = %d""" % (row.impulseid, row.scanid)
                self.engine.execute(sql)
                self.WriteLog(sql)

    def GetMatchTable(self):
        impulses_query = """
            select impulses.impulsetime as impulses_impulsetime,
                   impulses.ms as impulses_ms,
                   scans.bib as scans_bib,
                   scans.scantime as scans_scantime,
                   impulses.id as impulses_id,
                   scans.id as scans_id,
                   scans.impulse as scans_impulse
            from impulses
                left outer join scans
                    on scans.impulse = impulses.id
            where impulses.erased is NULL
            order by impulses_impulsetime, impulses_ms, impulses_id"""
        others_query = """
            select scans.scantime as scans_scantime,
                   scans.bib as scans_bib,
                   scans.id as scans_id
            from scans
            where scans.impulse is null
            order by scans_scantime, scans_id"""

        impulses = self.engine.execute(impulses_query)
        other_scans = self.engine.execute(others_query)

        impulses_results = impulses.fetchall()
        other_scans_results = other_scans.fetchall()

        impulseresults_iterator = enumerate(impulses_results)
        otherscanresults_iterator = enumerate(other_scans_results)

        impulse_count = 0
        bibscan_count = 0
        unmatchedscan_count = 0

        try:
            ii, irow = impulseresults_iterator.next()
            impulse_count += 1
            assert not IsFlagValue(irow.scans_bib)
            if not None is irow.scans_bib:
                bibscan_count += 1
                if trace: print "0 bump bibscan for %s" % repr(irow.scans_bib)
        except StopIteration:
            ii = -1

        try: 
            si, srow = otherscanresults_iterator.next()
            if not IsFlagValue(srow.scans_bib):
                bibscan_count += 1
                unmatchedscan_count += 1
                if trace:
                    print "0 bump bibscan, unmatched for %d" %\
                        srow.scans_bib
        except StopIteration:
            si = -1

        # result items are (impulsetime or NULL, bib or NULL, scantime or NULL,
        # impulseid or NULL, scanid or NULL)
        result = []
        while si != -1 or ii != -1:
            itime = irow.impulses_impulsetime.replace(microsecond=irow.impulses_ms)
            if (si == -1
                or (itime <= srow.scans_scantime
                    if ii != -1 else False)):
                result.append(RowProxy(["impulsetime",itime,
                                        "bib", irow.scans_bib,
                                        "scantime",irow.scans_scantime,
                                        "impulseid", irow.impulses_id,
                                        "scanid", irow.scans_id]))
                try:
                    ii, irow = impulseresults_iterator.next()
                    impulse_count += 1
                    if IsFlagValue(irow.scans_bib):
                        inconsistent()
                    elif not None is irow.scans_bib:
                        if trace: print "bump bibscan for %d" % irow.scans_bib
                        bibscan_count += 1
                except StopIteration: 
                    ii = -1
            elif (ii == -1
                  or (itime > srow.scans_scantime
                      if si != -1 else False)):
                result.append(RowProxy(["impulsetime", None,
                                        "bib", srow.scans_bib,
                                        "scantime", srow.scans_scantime,
                                        "impulseid", None, 
                                        "scanid", srow.scans_id]))
                try:
                    si, srow = otherscanresults_iterator.next()
                    if not IsFlagValue(srow.scans_bib):
                        if trace: print "bump bibscan, unmatched for %d" %\
                                srow.scans_bib
                        bibscan_count += 1
                        unmatchedscan_count += 1
                except StopIteration:
                    si = -1
        return (result, impulse_count, bibscan_count, unmatchedscan_count)

    def AssignImpulseToScanByRecordIDs(self, impulseid, scanid):
        """Glue a scan to an impulse in the database."""

        irow = self.engine.execute("select * from impulses where id = %d"
                                   % impulseid).fetchone()
        srow = self.engine.execute("select * from scans where id = %d"
                                   % scanid).fetchone()

        # Don't assign across a time when the corral was empty.
        itime = irow.impulsetime.replace(microsecond=irow.ms)
        stime = srow.scantime
        empties = self.engine.execute("""
            select bib 
            from scans 
            where bib = %d
              and scans.scantime > '%s'
              and scans.scantime < '%s'""" % (Db.FLAG_CORRAL_EMPTY,
                                              itime, stime)).fetchall()
        if len(empties) > 0:
            return False

#         set = { 'impulse': impulseid }
#         self.session.query(Db.Scan).filter("id = %s" % scanid).update(set)
        sql = """
            update scans
            set impulse = %d
            where id = %d""" % (impulseid, scanid)
        self.engine.execute(sql)
        self.WriteLog(sql)

        self.notifier.NotifyAll()
        return True

    def AssignImpulseToScanByIndices(self, tableresults, impulserow, scanrow):
        """tableresults is result from GetMatchTable above.  Try to
        assign a scan to an impulse; if it works, adjust tableresults
        to match."""

        # Table is sorted by time. Impulse can't come after scan.
        if impulserow >= scanrow:
            return False

        # impulserow must contain an impulse.
        impulsetime = tableresults[impulserow].impulsetime
        if impulsetime is None:
            return False

        # impulserow must not contain a bib number (by row type or assignment)
        if not None is tableresults[impulserow].bib:
            return False

        # scanrow must contain a non-flag bib number.
        bib = tableresults[scanrow].bib
        if bib is None:
            return False
        if IsFlagValue(bib):
            return False

        # scanrow must not contain an impulse time (by row type or assignment)
        if not None is tableresults[scanrow].impulsetime:
            return False
        
        impulseid = tableresults[impulserow]['impulseid']
        scanid = tableresults[scanrow]['scanid']

        result = self.AssignImpulseToScanByRecordIDs(impulseid, scanid)
        if result:
            tableresults[impulserow]['bib'] = bib
            tableresults[impulserow]['scantime']= tableresults[scanrow].scantime
            tableresults[impulserow]['scanid'] = scanid
            tableresults.pop(scanrow)
        return result

    def UnassignImpulseByRow(self, tableresults, row):
        scanid = tableresults[row]['scanid']

#        set = { 'impulse': None }
#        self.session.query(Db.Scan).filter("id = %s" % scanid).update(set)
        sql = "update scans set impulse = NULL where id = %s" % scanid
        self.engine.execute(sql)
        self.WriteLog(sql)

        self.notifier.NotifyAll()
        del(tableresults[:])    # now caller must reload

#     def DuplicateImpulseByID(self, tablerow):
#         impulsetime = tablerow['impulsetime']
#         self.session.add(Db.Impulse(impulsetime))
#         self.session.commit()

    def EraseImpulseByID(self, impulseid):
        sql = """
            update impulses
            set erased='%s'
            where id=%s""" % (datetime.now().isoformat(), impulseid)
        self.engine.execute(sql)
        self.WriteLog(sql)
        self.notifier.NotifyAll()

    def Save(self):
        db.session.commit()

    def IsUnsaved(self):
        db.session.dirty()

    def _generateResults_combosToBitmasks(self, all, want_combos):
        """Make bit masks corresponding to "ord" values in
        GenerateResults below that represent report category
        combinations in want_combos.  all is a list of all category
        names; want_combos is a list of lists of subsets of these
        categories."""
        names = {}
        iter = enumerate(all)
        try:
            i, name = next(iter)
            while True:
                names[name] = (1 << i)
                i, name = next(iter)
        except StopIteration:
            pass
        print "combosToBitmasks names:", names
        results = []
        for combo in want_combos:
            mask = 0
            for name in combo:
                if name in names:
                    mask |= names[name]
            results.append(mask)
        return results

    def GenerateResults(self, want_combos):
        """Get top finishers by all combinations of categories. If
        want_combos is non-None then limit the report to those
        combinations of categories from ENTRIES_FINISH_CATEGORIES, like
        ((), ('agegp'), ('agegp','bike')). (The first means Overall.)"""

        all = ENTRIES_FINISH_CATEGORIES
        ord = orderByIncreasingBitCount(len(all))
        qgt = QueryGeneratorTop(self, 'entries', all)

        limit = None
        if not None is want_combos:
            restrict = self._generateResults_combosToBitmasks(all, want_combos)
        print "Restrict report to:", restrict

        self.StartReport(REPORT_TITLE)
        for i in ord:
            if not i in restrict:
                continue
            qg = QueryGenerator(qgt, i, self.CompileReport)
            qg.GenerateResultCombinations()
        self.ReportDNFs()
        self.FinishReport()

    def GenerateOverallResults(self):
        pass

    def StartReport(self, message):
        self.message = message
        self.reportTime = datetime.now()
        self.page = 0
        self.line = 0
        self.linesPerPage = 56
        self.rfd = open("./FinishReport.txt", "w")
        self.NewPage()

    def NewPage(self):
        if self.page > 0:
            self.rfd.write("\f")
        self.page += 1
        self.rfd.write("%-19.19s   %-40.40s %10.10s\n"
                       % (self.reportTime.isoformat(), self.message,
                          "page %d" % self.page))
        self.line = 1

    def ReportDNFs(self):
        sql = "select * from entries where dnf is not NULL"
        rows = self.engine.execute(sql).fetchall()
        return self.CompileReport({}, rows, -1)

    def CompileReport(self, where, rows, fullcount):
        if self.line + 2 + len(rows) >= self.linesPerPage:
            self.NewPage()
        # place oaplace bib name    time  gend cl/at cat   bike  agegp  res
        rowfmt= "%2d.%4s%4d %-21.21s%7.7s %1.1s%2.2s %5.5s %4.4s %5.5s %7.7s\n" 
        keys = sorted(where.keys())
        title = " ".join(map(lambda k: "%s:%s" % (k, where[k]), keys))
        if title == '':
            title = 'Overall'
        if fullcount == -1:
            title = "Did Not Finish"
            self.rfd.write("\n%-68.68s(%d)\n" % (title, len(rows)))
        else:
            self.rfd.write("\n%-68.68s(%d of %d)\n" % (title, len(rows),
                                                       fullcount))
        self.line += 2 + len(rows)
        riter = enumerate(rows)
        try:
            i, row = next(riter)
            while True:
                name = "%s,%s" % (row.lastname, row.firstname)
                if not None is row.totalsecs and row.dnf is None:
                    ts = row.totalsecs
                    time = "%d:%02d:%02d" % ((ts/3600)%24, (ts/60)%60, ts%60)
                elif not None is row.dnf:
                    time = " DNF "
                else:
                    time = "missing"
                self.rfd.write(rowfmt % (i+1, "(%d)" % 0, row.bib, name, time,
                                         row.gender,
                                         'AC' if row.ath_clyde != '' else '',
                                         row.cat, row.bike, row.agegp, 
                                         row.reside))
                i, row = next(riter)
        except StopIteration:
            pass

    def FinishReport(self):
        self.rfd.close()

    def RunArbitraryQuery(self, query):
        return self.engine.execute(query)

if __name__ == "__main__":

    def LoadTestData(db):
        db.session.add_all([
                Db.Entry(101, "Albert"),
                Db.Impulse("12:02:10"),
                Db.Scan("12:02:22", 102),
                ])
        db.session.commit()
        db.engine.execute("delete from entries")
        db.engine.execute("delete from impulses")
        db.engine.execute("delete from scans")
        db.session.add_all([
                Db.Entry(101, "Albert"),
                Db.Entry(102, "Bob"),
                Db.Entry(103, "Clyde"),
                Db.Entry(104, "Dale"),
                Db.Entry(105, "Ernie"),
                Db.Impulse("00:02:10"),
                Db.Impulse("00:03:33"),
                Db.Impulse("00:03:33"),
                Db.Impulse("00:14:44"),
                Db.Scan("00:02:22", 102),
                Db.Scan("00:02:25", Db.FLAG_CORRAL_EMPTY),
                Db.Scan("00:04:01", 104),
                Db.Scan("00:04:10", 101),
                Db.Scan("00:04:16", 104),
                Db.Scan("00:04:20", Db.FLAG_ERROR),
                Db.Scan("00:04:25", Db.FLAG_CORRAL_EMPTY),
                Db.Scan("00:14:59", 105),
                Db.Scan("00:15:03", Db.FLAG_CORRAL_EMPTY),
                ])
        db.session.commit()

    def msg(m):
        verbose=True
        if verbose:
            print m
        else:
            print '.',

#    db = Db('sqlite:///:memory:', echo=False)
    db = Db('mysql://anonymous@localhost/test', "db-test", echo=False)

    LoadTestData(db)
    db.session.commit()

    t = db.session.query(Db.Scan).\
        join(Db.Entry).\
        filter(Db.Entry.firstname == 'Dale').\
        first().scantime
    dale_scantime = DatetimeAsTimestring(t)
    msg("Dale's scan time: '%s' should be 00:04:01.000000" % dale_scantime)
    assert dale_scantime == "00:04:01.000000"

    # Pretend we're assigning finish impulses to riders by hand.
    # Clyde didn't finish.  Notice Albert and Dale were scanned out of
    # order, but they were in the finish corral at the same time so we
    # knew to pay attention to them.
    impulses = db.session.query(Db.Impulse).\
        order_by(Db.Impulse.impulsetime, Db.Impulse.ms, Db.Impulse.id).\
        all()
    observed_finishes = [ 'Bob', 'Albert', 'Dale', 'Ernie' ]
    for i in range(0,len(impulses)):
        entry = db.session.query(Db.Entry).\
            filter(Db.Entry.firstname == observed_finishes[i]).first()
        allscans = db.session.query(Db.Scan).\
            filter(Db.Scan.bib == entry.bib).all()
        allscans[-1].impulse = impulses[i].id
        msg("Assigned bib %d -> finish time %s" % (entry.bib,
                                                   impulses[i].impulsetime))
        db.session.commit()

    c = db.session.execute("""select entries.bib,
                                     impulses.impulsetime,
                                     entries.firstname,
                                     impulses.ms,
                                     impulses.id as impulses_id
                              from entries, impulses, scans
                              where entries.bib = scans.bib
                                and scans.impulse = impulses.id
                              order by impulsetime, ms, impulses_id""")
    results = c.fetchall()
#     results = db.session.query(Db.Impulse, Db.Entry).\
#         join(Db.Entry).\
#         order_by(Db.Impulse.impulsetime).\
#         all()

    msg("Finish Report:")
    for i in range(0,len(results)):
        msg("%3d: bib:%3d time:%s name:%-20s" % (i+1,
                                        results[i][0],
                                        results[i][1],
                                        results[i][2]))

    msg("Compare with observed finishes: %s" % repr(observed_finishes))
    assert(len(results) == len(observed_finishes))
    for i in range(0, len(observed_finishes)):
        assert(results[i][2] == observed_finishes[i])

