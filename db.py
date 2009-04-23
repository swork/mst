from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, relation, backref, join

Base = declarative_base()

class Db:
    """Hold the database session info.  Only one instance possible?"""
        
    def __init__(self, dbstring, echo):
        engine = create_engine(dbstring, echo=echo)
        Session = sessionmaker(bind=engine)
        self.session = Session()
        Base.metadata.create_all(engine)

    class Entry(Base):
        """Registration info for an entrant"""
        __tablename__ = 'entries'

        id = Column(Integer, primary_key=True)
        firstname = Column(String)
        bib = Column(Integer)

        def __init__(self, bib, firstname):
            self.bib = bib
            self.firstname = firstname

        def __repr__(self):
            return "<Db.Entry('%s','%s')>" % (self.firstname, self.bib)

    class Impulse(Base):
        """Time at which *someone* crossed the finish line. Assign bib later"""
        __tablename__ = 'impulses'

        id = Column(Integer, primary_key=True)
        impulsetime = Column(String)
        bib = Column(Integer, ForeignKey("entries.bib"))

        entry_bib = relation("Entry", backref=backref('impulses', order_by=bib))

        def __init__(self, impulsetime):
            self.impulsetime = impulsetime
            self.bib = None

        def __repr__(self):
            return "<Db.Impulse('%s', %s)>" % (self.impulsetime, repr(self.bib))

    class Scan(Base):
        """Bib number and time scanned as finisher leaves the finish corral"""
        __tablename__ = 'scans'

        id = Column(Integer, primary_key=True)
        scantime = Column(String)
        bib = Column(Integer, ForeignKey("entries.bib"))

        entry_bib = relation("Entry", backref=backref('scans', order_by=bib))

        def __init__(self, scantime, bib):
            self.scantime = scantime
            self.bib = bib

        def __repr__(self):
            return "<Db.Scan('%s',%d)>" % (self.scantime, self.bib)

    def BusyTimesList(self, trace=False):
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
                elif scan.bib == -1:
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
        

if __name__ == "__main__":

    db = Db('sqlite:///:memory:', echo=False)

    db.session.add_all([
        Db.Entry(101, "Albert"),
        Db.Entry(102, "Bob"),
        Db.Entry(103, "Clyde"),
        Db.Entry(104, "Dale"),
        Db.Entry(105, "Ernie"),
        Db.Impulse("12:02:10.02"),
        Db.Impulse("12:03:33.01"),
        Db.Impulse("12:03:33.03"),
        Db.Impulse("12:14:44.04"),
        Db.Scan("12:02:22.00", 102),
        Db.Scan("12:02:25.00", -1), # scanned card: "Finish corral empty"
        Db.Scan("12:04:01.00", 104),
        Db.Scan("12:04:10.00", 101),
        Db.Scan("12:04:15.00", -1),
        Db.Scan("12:14:59.00", 105),
        Db.Scan("12:15:03.00", -1),
        ])

    db.session.commit()

    t = db.session.query(Db.Scan).\
        join(Db.Entry).\
        filter(Db.Entry.firstname == 'Dale').\
        first().scantime
    print "Dale's scan time: '%s' should be 12:04:01.00" % t
    assert t == "12:04:01.00"

    # Pretend we're assigning finish impulses to riders by hand.
    # Clyde didn't finish.  Notice Albert and Dale were scanned out of
    # order, but they were in the finish corral at the same time so we
    # knew to pay attention to them.
    impulses = db.session.query(Db.Impulse).\
        order_by(Db.Impulse.impulsetime).\
        all()
    observed_finishes = [ 'Bob', 'Albert', 'Dale', 'Ernie' ]
    for i in range(0,len(impulses)):
        rider = db.session.query(Db.Entry).\
            filter(Db.Entry.firstname == observed_finishes[i]).first()
        impulses[i].bib = rider.bib
        print "Assigned bib %d -> finish time %s" % (impulses[i].bib,
                                                     impulses[i].impulsetime)

    db.session.commit()

    results = db.session.query(Db.Impulse, Db.Entry).\
        join(Db.Entry).\
        order_by(Db.Impulse.impulsetime).\
        all()

    print "Finish Report:"
    for i in range(0,len(results)):
        print "%3d: %3d %8.8s %-20s" % (i+1,
                                        results[i][0].bib,
                                        results[i][0].impulsetime, 
                                        results[i][1].firstname)

    print "Compare with observed finishes: %s" % repr(observed_finishes)

    print "Busy Times List: %s" % db.BusyTimesList(True)
