class MapFinish(object):
    """Get some control over combinatorial explosion"""
    def __init__(self):
        reside = {'AB':'', 'Canada':'', 'Other':''}
        ath_clyde = {'A':'Y', 'C':'Y'}
        cat = {'RecF':'Rec', 'CT':'Comp', 'SR-Tandem':'SR',
               'U-DUMB-Tandem':'U-DUMB'}
        bike = {'Mtn. Bike':'Mtn'}
        self.maps = {'reside':reside, 'ath_clyde':ath_clyde, 'cat':cat,
                     'bike':bike}

    def Map(self, colname, values):
        """distincts is a single-column Db query result. Map values to
        reduce set size."""
        if self.maps.has_key(colname):
            results = []
            didit = {}
            mappings = self.maps[colname]
            for val in values:
                if mappings.has_key(val):
                    newval = mappings[val]
                else:
                    newval = val
                if newval != '' and not didit.has_key(newval):
                    results.append(newval)
                    didit[newval] = 1
            print "colname:%s results:" % colname, results
            return results
        else:
            print "colname:%s values:" % colname, values
            return values
