"""Classes to calculate time spent in various countries."""

import collections
import datetime

import csvtable


class Interval(collections.namedtuple("Interval", "start end country")):

  """Represents a date interval."""

  DATE_FORMAT = "%Y-%m-%d"

  def __new__(cls, start, end, country):
    return super(cls, Interval).__new__(
        cls,
        datetime.datetime.strptime(start, cls.DATE_FORMAT),
        datetime.datetime.strptime(end, cls.DATE_FORMAT),
        country)

  def Intersect(self, start, end):
    if end >= self.start and start <= self.end:
      return max(start, self.start), min(end, self.end)
    return None

  def __len__(self):
    return (self.end - self.start).days + 1

  def Duration(self):
    return (self.end - self.start).days + 1


class TaxCalendar(object):

  """A tax to calculate time spent in various countries."""

  DATE_FORMAT = "%Y-%m-%d"

  def Debug(self, s):
    if self.debug: print s

  @staticmethod
  def IsCountryOrStateOf(country1, country2):
    """Returns true if country1 is country2 or a state of country2."""
    return (country1 == country2 or
            (country2 is not None and country1.startswith(country2 + "_")))

  def __init__(self, residence, businesstrips, debug=False):
    if not residence:
      raise ValueError("Need to have lived somewhere")
    if debug:
      print 'RESIDENCE,"Start date","End date"'
      for i in residence:
        print ",%s,%s,%s" % (i[0], i[1], i[2])
      print
      print 'BUSINESSTRIPS,"Start date","End date"'
      for i in businesstrips:
        print ",%s,%s,%s" % (i[0], i[1], i[2])
    self.residence = residence
    self.businesstrips = businesstrips
    self.residence.sort(key=lambda interval: interval.start)
    self.businesstrips.sort(key=lambda interval: interval.start)
    self.debug = debug

    def CheckIntervals(intervals):
      for interval in intervals:
        if len(interval) < 1:
          raise ValueError("Interval must be at least one day: %s" %
                           str(interval))
      for index, _ in enumerate(intervals[:-1]):
        if intervals[index].end > intervals[index + 1].start:
          raise ValueError("Overlapping intervals: %s and %s" %
                           (intervals[index], intervals[index + 1]))
    CheckIntervals(self.businesstrips)
    CheckIntervals(self.residence)

    # Check residence intervals are contiguous.
    for index, _ in enumerate(self.residence[:-1]):
      oldend = self.residence[index].end
      newstart = self.residence[index + 1].start
      if newstart - oldend != datetime.timedelta(1):
        raise ValueError("Residency intervals must be contiguous: %s and %s" %
                         (self.residence[index], self.residence[index + 1]))

    minyear = self.residence[0].start.year
    maxyear = min(self.residence[-1].end.year, datetime.date.today().year)
    self.years = range(minyear, maxyear + 1)

  @staticmethod
  def ReadFromCSV(filename):
    """Generates a TaxCalendar from a multi-table CSV file."""

    class LocationTable(csvtable.CSVTable):

      def __init__(self, name, headings):
        super(LocationTable, self).__init__(name, headings)
        self.data = []

      def AddRow(self, row):
        self.CheckRow(row)
        self.data.append(Interval(*row))

    data = csvtable.ReadMultitableCSV(filename, LocationTable)
    expected_tables = ["BUSINESSTRIPS", "RESIDENCE"]

    if sorted(data.keys()) != expected_tables:
      raise ValueError("Unexpected tables.\n  Expected: %s\n  Found: %s" % (
          sorted(data.keys()), expected_tables))

    return TaxCalendar(data["RESIDENCE"].data, data["BUSINESSTRIPS"].data)

  def GetYears(self):
    return self.years

  def FindLocations(self, start, end, taxcountry=None, include_trips=True):
    """Returns a a dict mapping locations to days in that location."""
    days = collections.defaultdict(int)
    for residence in self.residence:
      overlap = residence.Intersect(start, end)
      if not overlap:
        continue
      this_start, this_end = overlap
      numdays = (this_end - this_start).days + 1
      self.Debug("  Living in %s from %s to %s (%d days)." % (
          residence.country, str(this_start), str(this_end), numdays))
      if include_trips:
        self.Debug("    Business trips:")
        for trip in self.businesstrips:
          overlap = trip.Intersect(this_start, this_end)
          if overlap:
            trip_start, trip_end = overlap
            trip_days = (trip_end - trip_start).days + 1
            self.Debug("      Trip to %s from %s to %s (%d days), %s taxes" %
                       (trip.country, str(trip_start), str(trip_end), trip_days,
                        taxcountry))
            # PWC guidance: "Assuming you were a non-resident at the time of the
            # trip, those Japan days will not be considered under the assumption
            # that you would have qualified for treaty exemption from Japan
            # taxation." So don't count business trips to a country, only from
            # a country.
            if trip.country == "JP" and taxcountry == "JP":
              self.Debug("        Skipping business trip to %s when calculating"
                         " resident days for %s" % (trip.country, taxcountry))
              continue
            days[trip.country] += trip_days
            days[residence.country] -= (trip_days)
      assert numdays >= 0
      days[residence.country] += numdays
      expected_total = (end - start).days + 1
    if sum(days.values()) != expected_total:
      raise ValueError(
          "Total days between %s and %s don't match: %d, should be %d, got: " %
          (start, end, sum(days.values()), expected_total), days)
    how = "including trips" if include_trips else "not including trips"
    self.Debug("    Total days %s: %s" % (how, days.items()))
    return days

  def FindLocationsForYear(self, year):
    locations = self.FindLocations(datetime.datetime(year, 1, 1),
                                   datetime.datetime(year, 12, 31))
    if sum(locations.values()) not in [365, 366]:
      raise ValueError("Invalid number of days in %d: %d!" % (
          year, sum(locations.values())))
    return locations


# Smoke tests.
test_interval = Interval("2013-01-28", "2013-02-05", "FR")
assert datetime.timedelta(8) == test_interval.end - test_interval.start
