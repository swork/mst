from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, relation, backref, join
from sqlalchemy.databases import mysql
from sqlalchemy import sql
from datetime import datetime
import types, re

trace = False

Base = declarative_base()

timere = re.compile(r"(\d+):(\d+):(\d+)")
def ConvertToDatetime(timeValue):
    val = datetime.now()
    t = type(timeValue)
    if t == types.StringType:
        res = timere.match(timeValue)
        return val.replace(hour=int(res.group(1)), minute=int(res.group(2)),
                           second=int(res.group(3)), microsecond=0, tzinfo=None)
    if t == types.DateTimeType:
        return timeValue.replace(tzinfo=None)
    raise "TimeValueConvert can't figure it out..."

def DatetimeAsTimestring(dt):
    return dt.strftime("%H:%M:%S")

class Db:
    """Hold the database session info.  Only one instance possible?"""

    # Special "bib" numbers
    FLAG_CORRAL_EMPTY = 999
    FLAG_ERROR = 998
    FLAG_DONT_ASSIGN = 0

    def IsFlagValue(self, bibnumber): # s.b. class-static member fn
        if bibnumber is None:
            return False
        if (bibnumber == Db.FLAG_CORRAL_EMPTY
            or bibnumber == Db.FLAG_ERROR
            or bibnumber == Db.FLAG_DONT_ASSIGN):
            return True
        return False

    def __init__(self, dbstring, echo):
        self.engine = create_engine(dbstring, echo=echo)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        Base.metadata.create_all(self.engine)

    class Entry(Base):
        """Registration info for an entrant"""
        __tablename__ = 'entries'

        id = Column(Integer(11), primary_key=True)
        firstname = Column(String(40))
        bib = Column(Integer(11))

        def __init__(self, bib, firstname):
            self.bib = bib
            self.firstname = firstname

        def __repr__(self):
            return "<Db.Entry('%s','%s')>" % (self.firstname, self.bib)

    class Impulse(Base):
        """Time at which *someone* crossed the finish line. Assign bib later"""
        __tablename__ = 'impulses'

        id = Column(Integer(11), primary_key=True)
        impulsetime = Column(mysql.MSDateTime, nullable=False)

        def __init__(self, impulsetime):
            if type(impulsetime) != datetime:
                self.impulsetime = ConvertToDatetime(impulsetime)
            else:
                self.impulsetime = impulsetime

        def __repr__(self):
            return "<Db.Impulse('%s')>" % (self.impulsetime)

    class Scan(Base):
        """Bib number and time scanned as finisher leaves the finish corral"""
        __tablename__ = 'scans'

        id = Column(Integer(11), primary_key=True)
        scantime = Column(mysql.MSDateTime)
        bib = Column(Integer(11), ForeignKey("entries.bib"))
        impulse = Column(Integer(11), ForeignKey("impulses.id"))

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
            return "<Db.Scan('%s',%d)>" % (self.scantime, self.bib)

    def BusyTimesList(self):
        """Find time periods when finish corral contains more than one rider
        with finishes not yet assigned.  Each ends only when the
        corral is marked empty.  Does a rollback() so flush first."""
        impulses = db.session.query(Db.Impulse).\
            order_by(Db.Impulse.impulsetime).\
            all()
        impulses_enumeration = enumerate(impulses)
        scans = db.session.query(Db.Scan).\
            order_by(Db.Scan.scantime).\
            all()
        scans_enumeration = enumerate(scans)
        corral_counter = 0;
        start_busy = ''
        results = []

        try:
            si, scan = scans_enumeration.next()
        except StopIteration:
            si = -1

        try:
            ii, impulse = impulses_enumeration.next()
        except StopIteration:
            ii = -1

        while si != -1 or ii != -1:
            if (si == -1
                or (impulse.impulsetime <= scan.scantime
                    if ii != -1 else False)):
                corral_counter += 1
                if trace: print "0: %s (%d)" % (impulse, corral_counter)
                if corral_counter == 2:
                    # check for subsequent error, then...
                    start_busy = impulse.impulsetime
                    if trace: print "start_busy: %s" % start_busy
                try:
                    ii, impulse = impulses_enumeration.next()
                except StopIteration:
                    ii = -1
            elif (ii == -1
                  or (impulse.impulsetime > scan.scantime
                      if si != -1 else False)):
                if scan.bib > 0:
                    corral_counter -= 1
                elif scan.bib == Db.EMPTY_CORRAL:
                    # check for subsequent error, then...
                    corral_counter = 0
                    if start_busy != '':
                        results.append((start_busy, scan.scantime))
                        start_busy = ''
                        if trace: print "end_busy: %s" % scan.scantime
                if trace: print "1: %s (%d)" % (scan, corral_counter)
                try:
                    si, scan = scans_enumeration.next()
                except StopIteration:
                    si = -1

        return results
            
#    def OutOfSyncTimesList(self):

    def GetRecentImpulseActivityTable(self, numRows):
        impulses = self.engine.execute("select impulses.impulsetime, scans.bib, impulses.id, scans.impulse from impulses left outer join scans on scans.impulse = impulses.id order by impulsetime desc, id desc limit %d" % numRows)
        impulses_results = impulses.fetchall()
        results = []
        for r in impulses_results:
            row = {  'impulseid': r[2], 'impulsetime': r[0], 'bib': r[1],
                     'competitor': '' }
            results.append(row)
        if trace: print results
        return results

    def RecordImpulse(self, impulseTime=None):
        if impulseTime is None:
            impulseTime = datetime.now()
        print impulseTime
        self.engine.execute("insert into impulses (impulsetime) values ('%s')" % impulseTime.isoformat())

    def GetMatchTable(self):
        impulses = self.engine.execute("select impulses.impulsetime, scans.bib, scans.scantime, impulses.id as impulses_id, scans.id, scans.impulse from impulses left outer join scans on scans.impulse = impulses.id order by impulsetime, impulses_id")
        other_scans = self.engine.execute("select scans.scantime, scans.bib, scans.id as scans_id from scans where scans.impulse is null order by scantime, scans_id")

        impulses_results = impulses.fetchall()
        other_scans_results = other_scans.fetchall()

        impulseresults_iterator = enumerate(impulses_results)
        otherscanresults_iterator = enumerate(other_scans_results)

        impulse_count = 0
        bibscan_count = 0
        unmatchedscan_count = 0

        try:
            ii, impulseresult = impulseresults_iterator.next()
            impulse_count += 1
            assert not self.IsFlagValue(impulseresult[1])
            if not None is impulseresult[1]:
                bibscan_count += 1
                if trace: print "0 bump bibscan for %s" % repr(impulseresult[1])
        except StopIteration:
            ii = -1

        try: 
            si, otherscanresult = otherscanresults_iterator.next()
            if not self.IsFlagValue(otherscanresult[1]):
                bibscan_count += 1
                unmatchedscan_count += 1
                if trace:
                    print "0 bump bibscan, unmatched for %d" %\
                        otherscanresult[1]
        except StopIteration:
            si = -1

        # result items are (impulsetime or NULL, bib or NULL, scantime or NULL, impulseid or NULL, scanid or NULL)
        result = []
        while si != -1 or ii != -1:
            if (si == -1
                or (impulseresult[0] <= otherscanresult[0]
                    if ii != -1 else False)):
                result.append({"impulsetime" : impulseresult[0],
                               "bib"         : impulseresult[1],
                               "scantime"    : impulseresult[2],
                               "impulseid"   : impulseresult[3],
                               "scanid"      : impulseresult[4]})
                try:
                    ii, impulseresult = impulseresults_iterator.next()
                    impulse_count += 1
                    if self.IsFlagValue(impulseresult[1]):
                        inconsistent()
                    elif not None is impulseresult[1]:
                        if trace: print "bump bibscan for %d" % impulseresult[1]
                        bibscan_count += 1
                except StopIteration: 
                    ii = -1
            elif (ii == -1
                  or (impulseresult[0] > otherscanresult[0]
                      if si != -1 else False)):
                result.append({"impulsetime" : None,
                               "bib"         : otherscanresult[1],
                               "scantime"    : otherscanresult[0],
                               "impulseid"   : None,
                               "scanid"      : otherscanresult[2]})
                try:
                    si, otherscanresult = otherscanresults_iterator.next()
                    if not self.IsFlagValue(otherscanresult[1]):
                        if trace: print "bump bibscan, umnatched for %d" %\
                                otherscanresult[1]
                        bibscan_count += 1
                        unmatchedscan_count += 1
                except StopIteration:
                    si = -1
        return (result, impulse_count, bibscan_count, unmatchedscan_count)

    def AssignImpulseToScanByIDs(self, tableresults, impulserow, scanrow):
        """tableresults is result from GetMatchTable above.  Glue a scan
        to an impulse in the database and adjust tableresults to match."""
        impulseid = tableresults[impulserow]['impulseid']
        scanid = tableresults[scanrow]['scanid']
        set = { 'impulse': impulseid }
        self.session.query(Db.Scan).filter("id = %s" % scanid).update(set)
        tableresults[impulserow]['bib'] = tableresults[scanrow]['bib']
        tableresults[impulserow]['scantime'] = tableresults[scanrow]['scantime']
        tableresults[impulserow]['scanid'] = scanid
        tableresults.pop(scanrow)
        if trace: print "Popped row %d, %d left" % (scanrow, len(tableresults))

    def UnassignImpulseByRow(self, tableresults, row):
        scanid = tableresults[row]['scanid']
        set = { 'impulse': None }
        self.session.query(Db.Scan).filter("id = %s" % scanid).update(set)
        del(tableresults[:])    # now caller must reload

    def DuplicateImpulseByID(self, tablerow):
        impulsetime = tablerow['impulsetime']
        self.session.add(Db.Impulse(impulsetime))
        self.session.commit()

    def Save(self):
        db.session.commit()

    def IsUnsaved(self):
        db.session.dirty()

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
        verbose=False
        if verbose:
            print m
        else:
            print '.',

#    db = Db('sqlite:///:memory:', echo=False)
    db = Db('mysql://anonymous@localhost/test', echo=False)

    LoadTestData(db)
    db.session.commit()

    t = db.session.query(Db.Scan).\
        join(Db.Entry).\
        filter(Db.Entry.firstname == 'Dale').\
        first().scantime
    assert DatetimeAsTimestring(t) == "00:04:01"
    msg("Dale's scan time: '%s' should be 00:04:01" % t)

    # Pretend we're assigning finish impulses to riders by hand.
    # Clyde didn't finish.  Notice Albert and Dale were scanned out of
    # order, but they were in the finish corral at the same time so we
    # knew to pay attention to them.
    impulses = db.session.query(Db.Impulse).\
        order_by(Db.Impulse.impulsetime).\
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

    c = db.session.execute("select entries.bib, impulses.impulsetime, entries.firstname from entries, impulses, scans where entries.bib = scans.bib and scans.impulse = impulses.id order by scans.impulse")
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

    msg("Busy Times List: %s" % db.BusyTimesList())
