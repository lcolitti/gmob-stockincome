import collections
import datetime
import locale

import csvtable

CURRENCIES = {
    "JP": "JPY",
    "US": "USD",
    "US_CA": "USD",
}

LOCALES = {
    "JP": "ja_JP.UTF-8",
    "US": "en_US",
    "US_CA": "en_US",
}


class GrantTable(csvtable.CSVTable):

  DATE_FORMAT = "%m/%d/%Y"

  def __init__(self, name, headings):
    super(GrantTable, self).__init__(name, headings)
    self.data = collections.OrderedDict()

  def AddRow(self, row):
    self.CheckRow(row)
    grant, date = row
    try:
      date = datetime.datetime.strptime(date, self.DATE_FORMAT)
    except ValueError:
      raise ValueError("Can't parse date '%s' in data row %s" % date, row) 
    self.data[grant] = date

  @staticmethod
  def ReadFromCSV(filename):
    return csvtable.ReadMultitableCSV(filename, GrantTable)


class StockTable(csvtable.CSVTable):

  DATE_FORMAT = "%d-%b-%y"  # 25-Jan-13.
  STATEMENT_COUNTRY = "US"  # To parse currency data and for month names.

  DATE_COLUMNS = {
      "GSUS": "Vest Date",
      "OPTIONS": "Exercise Date",
  }
  GRANT_COLUMNS = {
      "GSUS": "Award Number",
      "OPTIONS": "Grant Number",
  }
  INCOME_COLUMN = "Reportable Income (employee)"

  @staticmethod
  def _ExpectColumn(headings, index, expected):
    if headings[index] != expected:
      raise ValueError("Column #%d must be '%s', found '%s'"
                       % (index, expected, headings[index]))

  def __init__(self, name, headings, converter, calendar, grants):
    super(StockTable, self).__init__(name, headings)

    # The stock events. A dictionary of data rows indexed by purno and country.
    self.data = collections.OrderedDict()

    # The column headings.
    self._ExpectColumn(headings, 0, "Purno")
    self._ExpectColumn(headings, 1, "Country")
    self.date_column = self.FindDateColumn()

    # The countries in the table.
    self.countries = collections.OrderedDict()

    # Currency converter, tax calendar, and grant information.
    self.converter = converter
    self.calendar = calendar
    self.grants = grants

    # By default, check percentages.
    self.check_percentages = True

  @staticmethod
  def ReadFromCSV(report_filename, grant_data, converter, calendar):

    def CheckExpectedTables(data, expected):
      if sorted(data.keys()) != sorted(expected):
        raise ValueError("Unexpected tables.\n  Expected: %s\n  Found: %s" % (
            sorted(data.keys()), expected))

    def CreateStockTable(name, headings):
      return StockTable(name, headings, converter, calendar, grant_data)

    data = csvtable.ReadMultitableCSV(report_filename, CreateStockTable)
    CheckExpectedTables(grant_data, data.keys())

    return data

  def FindColumn(self, name):
    return self.headings.index(name) - 2

  def FindIncomeColumn(self):
    return self.FindColumn(self.INCOME_COLUMN)

  def FindDateColumn(self):
    return self.FindColumn(self.DATE_COLUMNS[self.name])

  def FindGrantColumn(self):
    return self.FindColumn(self.GRANT_COLUMNS[self.name])

  def AddRow(self, row):
    self.CheckRow(row)

    purno, country, data = row[0], row[1], row[2:]
    if purno not in self.data:
      self.data[purno] = collections.OrderedDict()
    if country in self.data[purno]:
      raise ValueError("Double taxation for purno %s in %s!" % (purno, country))

    # Convert string dates to dates here so we only do it once.
    data[self.date_column] = datetime.datetime.strptime(
        data[self.date_column], self.DATE_FORMAT)

    self.countries[country] = True
    self.data[purno][country] = data
    # TODO: check that the award number, date, etc. are the same

  def SetCheckPercentages(self, check_percentages):
    self.check_percentages = check_percentages

  def GetAllCountries(self):
    return list(self.countries.keys())

  def GetCurrencyValue(self, value):
    if value[0] == "$":
      return locale.atof(value[1:])
    else:
      raise ValueError("Don't understand cell value %s" % value)

  def GetGrantDate(self, grant):
    try:
      return self.grants[self.name][grant]
    except KeyError:
      raise KeyError("Can't find grant date of grant %s" % grant)

  def GetCountryPercentage(self, row, country):
    date = row[self.date_column]
    grant = row[self.FindGrantColumn()]
    grant_date = self.GetGrantDate(grant)
    total_days = (date - grant_date).days + 1
    # Check against Google numbers.
    if self.check_percentages and country == "US_CA":
      notrip_days = self.calendar.FindLocations(grant_date, date,
                                                taxhome=country,
                                                include_trips=False)[country]
      percentage = float(notrip_days) / total_days * 100
      google_percentage = float(row[9][:-1])
      if round(percentage, 2) != round(google_percentage, 2):
        raise ValueError("Percentage mismatch for %s: %.2f vs %2f (%d days)" % (
            row[0], percentage, google_percentage, notrip_days))
    country_days = self.calendar.FindLocations(grant_date, date,
                                               taxhome=country)[country]
    percentage = float(country_days) / total_days
    return percentage

  def SetLocaleForCountry(self, country):
    try:
      loc = LOCALES[country]
      locale.setlocale(locale.LC_ALL, loc)
    except locale.Error:
      raise locale.Error("Need locale '%s' to use currency for country'%s'" %
                         (loc, country))
    except KeyError:
      raise NotImplementedError("Don't know what locale to use for country %s"
                                % country)

  def GetCountryTotal(self, country, column):
    loc = locale.getlocale(locale.LC_ALL)
    try:
      self.SetLocaleForCountry(self.STATEMENT_COUNTRY)
      total = 0.0
      try:
        currency = CURRENCIES[country]
      except KeyError:
        raise NotImplementedError("Don't know the currency for country %s"
                                  % country)
      for purno, country_data in self.data.iteritems():
        for transaction_country in country_data:
          if (transaction_country == country or
              transaction_country.startswith(country + "_")):
            data = country_data[country]
            date = data[self.date_column]
            percentage = self.GetCountryPercentage(data, transaction_country)
            usd_value = self.GetCurrencyValue(data[column])
            value = self.converter.ConvertCurrency(usd_value, "USD",
                                                   currency, date, "TTM")
            total += value * percentage
      self.SetLocaleForCountry(country)
      out = locale.currency(total, grouping=True)
    finally:
      locale.setlocale(locale.LC_ALL, loc)
    return out

  def PrintEvents(self):
    for purno in self.data:
      event = self.data[purno]
      randomcountry = event.keys()[0]
      randomrow = event[randomcountry]
      print purno, randomrow[0], randomrow[2], randomrow[6]
      for country in event:
        print "  %s: %.2f%%" % (
            country, self.GetCountryPercentage(event[country], country) * 100)

  def __str__(self):
    out = "%s = {\n" % self.name
    for purno in self.data:
      out += "    '%s': [\n" % purno
      for row in self.data[purno]:
        out += "        %s,\n" % row
      out += "    ],\n"
    out += "}"
    return out
