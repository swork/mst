import wx
import sqlalchemy

class Actions(object):
    def __init__(self, dbobject):
        """Index, Menu name, query, rows in result if not None (generally 0)"""
        self.db = dbobject
        self.all = (

            { 'id': wx.NewId(),
              'title': u'Set Start Times From Groups Table',
              'desc': """
    First clear start time of day values from table 'entries' for all
    competitors. Then for each competitor in table 'entries,' find the
    group start time of day from the groups table by matching
    groups.startkey with entries.cat. All competitors should be
    affected, so finally validate that the count of rows changed
    matches the total count of rows in table 'entries.' This query is
    safe to run after the event begins ONLY if no competitor's start
    time has been entered by hand.
             """,
              'queries': ("""
                     update entries set entries.starttod = NULL
              """, """
                     update entries, groups
                     set entries.starttod = groups.starttod
                     where entries.cat = groups.startkey
              """),
              'validate': self.CheckStartResults
              },

            { 'id': wx.NewId(), 
              'title': u'Find All Finish Times-of-day',
              'desc': """
    First clear finish time-of-day values from table 'entries' for all
             competitors. The for each competitor in table 'entries,'
             find the latest time in table 'impulses' that is already
             matched to this competitor's bib number and place this
             value in entries.finishtod. At the end of the event all
             competitors should either have a non-NULL finishtod field
             or a non-NULL dnf field, so validate that this is so and,
             on failure, list the competitors unaccounted for. 
             """,
              'procedure': self.DoFindFinishes,
              'validate': self.CheckFindFinishes
              },
                     
         )
        self.byId = dict(map(lambda x: (x['id'], x), self.all))
        self.menu = None        # lazy load

    def CheckStartResults(self):
        """Validate the results of the Set Start Times query"""
        msg = ''

        sql_total = "select count(*) from entries"
        total_count = self.db.engine.execute(sql_total).scalar()
        msg += "We have %d entries in the database. " % total_count

        msg += "First we cleared start times. "

        msg += "Then we set start times from 'groups' values. "

        sql_missing = """
                select id, bib, lastname, firstname, cat
                from entries where starttod is NULL"""
        rows = self.db.engine.execute(sql_missing).fetchall()

        if len(rows) > 10:
            msg += ("Now %d entries have no starttod, too many to list.\n"
                    % len(rows))
            msg += "RESULT NOT SUCCESSFUL.\n"
        elif len(rows) > 0:
            msg += "%d entries have no starttod, RESULT NOT SUCCESSFUL:\n\n" % \
                len(rows)
            for row in rows:
                    msg += ("%5d %4d %-10.10s %-10.10s %10.10s\n"
                            % (row.id, row.bib, row.lastname, row.firstname, 
                               row.startkey))
        else:
            msg += "All entries now have starttod assigned. OK.\n"
        print msg

    def GetActionsMenu(self):
        if self.menu is None:
            self.menu = wx.Menu()
            for item in self.all:
                self.menu.Append(item['id'], item['title'], item['desc'])
        return self.menu

    def GetActionsIds(self):
        return map(lambda x: x['id'], self.all)

    def OnId(self, evt):
        if self.byId.has_key(evt.GetId()):
            item = self.byId[evt.GetId()]
            results = []
            if item.has_key('procedure'):
                item['procedure']()
            elif item.has_key('queries'):
                qiter = enumerate(item['queries'])
                try:
                    i, query = next(qiter)
                    while True:
                        try:
                            print "query %d:" % i, query
                            results.append(self.db.RunArbitraryQuery(query))
                            print "query %d done." % i
                        except sqlalchemy.exc.OperationalError:
                            if (not item.has_key('failureOK')
                                or item['failureOK'][i] == 0):
                                raise
                        i, query = next(qiter)
                except StopIteration:
                    pass
            else:
                raise Exception("Check queries.py table values...")
            if not None is item['validate']:
                item['validate']()

    def DoFindFinishes(self):
        """Can't get MySQL to do a correlated subquery on an UPDATE statement,
        so doing this procedurally."""
        engine = self.db.engine

        sql_wipe_finishes = """
            update entries set finishtod = NULL, ms = NULL, totalsecs = NULL"""
        result = engine.execute(sql_wipe_finishes)

        sql_get_finishes = """
            select impulses.impulsetime as impulsetime,
                   impulses.ms as ms,
                   scans.bib as bib
                from impulses, scans
                where impulses.id = scans.impulse
                order by bib asc,
                         impulsetime desc,
                         ms desc"""
        results = engine.execute(sql_get_finishes).fetchall()

        sql_update = """
            update entries set finishtod = '%s', ms = %s where bib = %s"""
        havebib = None
        for row in results:
            if row.bib != havebib and not None is row.bib:
                sql = sql_update % (row.impulsetime, row.ms, row.bib)
                engine.execute(sql)
                havebib = row.bib

        sql_totalsecs = """
                     update entries
                     set totalsecs = time_to_sec(timediff(finishtod, starttod))
                     where starttod is not NULL and finishtod is not NULL"""
        engine.execute(sql_totalsecs)

    def CheckFindFinishes(self):
        """Validate the results of the Set Finish Times query"""
        msg = ''

        sql_total = "select count(*) from entries"
        total_count = self.db.engine.execute(sql_total).scalar()
        msg += "We have %d entries in the database. " % total_count

        msg += "First we cleared all finish times. "

        msg += "Then we set finish times from impulses and scans table values. "

        sql_missing = """
                select id, bib, lastname, firstname, cat
                from entries where totalsecs is NULL"""
# dnf is NULL and (
        rows = self.db.engine.execute(sql_missing).fetchall()

        if len(rows) > 10:
            msg += ("Now %d entries have no finish time, too many to list.\n"
                    % len(rows))
            msg += "RESULT NOT SUCCESSFUL.\n"
        elif len(rows) > 0:
            msg += "%d entries have no finish time, RESULT NOT SUCCESSFUL:\n\n"\
                % len(rows)
            for row in rows:
                    msg += ("%5d %4d %-10.10s %-10.10s %10.10s\n"
                            % (row.id, row.bib, row.lastname, row.firstname, 
                               row.startkey))
        else:
            msg += "All entries now have finish time assigned. OK.\n"
        print msg

