# encoding: utf-8

import collections
import datetime
import locale
import StringIO

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

COUNTRY_NAMES = {
    "JP": "Japan",
    "US": "USA",
    "US_CA": "California",
}

def GetCountryCurrency(country):
  try:
    return CURRENCIES[country]
  except KeyError:
    raise NotImplementedError("Don't know the currency for country %s"
                              % country)

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

  STATEMENT_FILES = {
      2013: {None: "google_year_end_stock_statement.csv"},
      2014: {"GSUS": "gmob_gsu_data_lorenzo.csv",
             "OPTIONS": "gmob_options_data_lorenzo.csv"},
  }

  GOOGLE_PERCENTAGE_HEADING_2013 = ("Percentage of total gain subject to tax "
                                    "withholding in this country or US state")
  GOOGLE_PERCENTAGE_HEADING_2014 = ("Percentage Total Gain Subject to Tax "
                                    "Witholding in this Country or US State")

  COLUMNS = {
      "DATE": {
          "GSUS": "Vest Date",
          "OPTIONS": "Exercise Date",
      },
      "GRANT" : {
          "GSUS": "Award Number",
          "OPTIONS": "Grant Number",
      },
      "NUMBER": {
          "GSUS": "GSU's Vested",
          "OPTIONS": "Options Exercised",
      },
      "PRICE": {
          "GSUS": "Award Price",
          "OPTIONS": "Option Price",
      },
      "TOTAL": {
          "GSUS": "Total gain (value) of GSUs at vest",
          "OPTIONS": "Total exercisable gain (value)",
      },
      "GOOGLE_PERCENTAGE": {
          "GSUS": {
              2013: GOOGLE_PERCENTAGE_HEADING_2013,
              2014: GOOGLE_PERCENTAGE_HEADING_2014,
          },
          "OPTIONS": {
              2013: GOOGLE_PERCENTAGE_HEADING_2013,
              2014: GOOGLE_PERCENTAGE_HEADING_2014,
          },
      },
  }

  REPORT_TITLES = {
      "GSUS": "Google Stock Units",
      "OPTIONS": "Google Stock Options",
  }

  REPORT_COLUMNS = {
      "US": [
          ("DATE", "Date"),
          ("_AWARD_DATE", "Award date"),
          ("NUMBER", "Shares"),
          ("PRICE", "Price"),
          ("Fair Market Value", "FMV"),
          ("TOTAL", "Total"),
          ("_TOTAL_DAYS", "Vesting days"),
          ("_COUNTRY_DAYS", "Days as resident"),
          ("_TRIP_DAYS", "Foreign work days"),
          ("_TAXABLE", "Taxable income"),
      ],
      "JP": [
          ("DATE", "権利行使日<br>(Exercise date)"),
          ("TOTAL", "利益の額<br>(Gain)"),
          ("_AWARD_DATE", "付与日<br>(Grant date)"),
          ("_TOTAL_DAYS", "付与日から行使日までの総日数<br>(Vesting days)"),
          ("_COUNTRY_DAYS",
           "入国から行使日までの日数<br>(Vesting days as Japan resident)"),
          ("_TRIP_DAYS", "国外勤務日数<br>(Vesting days working abroad)"),
          ("_TAXABLE", "国内源泉所得に係る金額<br>(Japan-source income, $)"),
          ("_FX_RATE", "換算レート<br>(Exchange rate)"),
          ("_LOCAL_TAXABLE", "国内源泉所得に係る金額<br>(Japan-source income)"),
      ]
  }

  REPORT_TEMPLATE = """\
<html>
  <head>
    <meta charset="UTF-8">
    <title>%(country)s-source income for %(title)s</title>
    <style type="text/css">
      h1 { font-family: sans-serif; font-size: x-large; }
      td { font-size: x-small; text-align: right;}
      tr:first-child td { text-align: center; background-color: lightgray; }
      table, td, th {
          border: 1px solid; border-collapse:collapse; padding: 0.29em;
      }
      table tr:first-child td {
        border-color: black;
      }
      table td {
        background-color: #f9f9f9;
        border-color: #dbdbdb;
      }

      table tr:nth-of-type(even) td {
        background-color: #f5f5f5;
        border-color: #d5d5d5;
      }
    </style>
  </head>
  <body>
    <h1>%(country)s-source income for %(title)s</h1>
    <table>
    %(rows)s
    </table>
  </body>
</html>
"""

  @staticmethod
  def _ExpectColumn(headings, index, expected):
    if headings[index] != expected:
      raise ValueError("Column #%d must be '%s', found '%s'"
                       % (index, expected, headings[index]))

  def __init__(self, name, year, headings, converter, calendar, grants):
    super(StockTable, self).__init__(name, headings)

    # What year is it?
    self.year = year

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

  @classmethod
  def ReadFromCSV(cls, year, grant_data, converter, calendar):

    def CheckExpectedTables(data, expected):
      if sorted(data.keys()) != sorted(expected):
        raise ValueError("Unexpected tables.\n  Expected: %s\n  Found: %s" % (
            sorted(data.keys()), expected))

    def CreateStockTable(name, headings):
      return StockTable(name, year, headings, converter, calendar, grant_data)

    try:
      statements = cls.STATEMENT_FILES[year]
    except KeyError:
      raise NotImplementedError(
          "Don't know what files to use for tax year %d" % year)

    filenames = statements.values()
    if len(filenames) == 1:
      data = csvtable.ReadMultitableCSV(filenames[0], CreateStockTable)
    else:
      tablenames, filenames = statements.keys(), filenames
      constructors = [CreateStockTable] * len(statements)
      data = csvtable.ReadCSVTables(tablenames, filenames, constructors)
    CheckExpectedTables(grant_data, data.keys())

    return data

  def FindColumn(self, heading):
    return self.headings.index(heading) - 2

  def FindColumnByType(self, columntype):
    heading = self.COLUMNS[columntype][self.name]
    if isinstance(heading, dict):
      heading = heading[self.year]
    elif not isinstance(heading, str):
      raise NotImplementedError("Can't find column heading %s in %s" %
                                (columntype, self.name))
    return self.FindColumn(heading)

  def FindTotalColumn(self):
    return self.FindColumnByType("TOTAL")

  def FindDateColumn(self):
    return self.FindColumnByType("DATE")

  def FindGrantColumn(self):
    return self.FindColumnByType("GRANT")

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

  def GetCurrencyValue(self, value):
    loc = locale.getlocale(locale.LC_ALL)
    self.SetLocaleForCountry(self.STATEMENT_COUNTRY)
    try:
      if value[0] == "$":
        return locale.atof(value[1:])
      else:
        raise ValueError("Don't understand cell value %s" % value)
    finally:
      locale.setlocale(locale.LC_ALL, loc)

  def CurrencyValueToString(self, value, country):
    loc = locale.getlocale(locale.LC_ALL)
    try:
      self.SetLocaleForCountry(country)
      return locale.currency(value, grouping=True)
    finally:
      locale.setlocale(locale.LC_ALL, loc)

  def GetGrantDate(self, grant):
    try:
      return self.grants[self.name][grant]
    except KeyError:
      raise KeyError("Can't find grant date of grant %s" % grant)

  def GetTotalDays(self, row):
    date = row[self.date_column]
    grant = row[self.FindGrantColumn()]
    grant_date = self.GetGrantDate(grant)
    total_days = (date - grant_date).days + 1
    return total_days

  def GetTotal(self, row):
    return self.GetCurrencyValue(row[self.FindTotalColumn()])

  def GetCountryDays(self, row, country, include_trips):
    date = row[self.date_column]
    grant = row[self.FindGrantColumn()]
    grant_date = self.GetGrantDate(grant)
    locations = self.calendar.FindLocations(grant_date, date,
                                            taxhome=country,
                                            include_trips=include_trips)
    return sum(locations[c] for c in locations
               if self.calendar.IsCountryOrStateOf(c, country))

  def GetCountryPercentage(self, row, country):
    total_days = self.GetTotalDays(row)
    country_days = self.GetCountryDays(row, country, True)
    percentage = float(country_days) / total_days

    # Check against Google numbers.
    if country == "US_CA" or country == "US":
      notrip_days = self.GetCountryDays(row, country, False)
      notrip_percentage = float(notrip_days) / total_days
      google_percentage_column = self.FindColumnByType("GOOGLE_PERCENTAGE")
      google_percentage = float(row[google_percentage_column][:-1])
      if round(notrip_percentage * 100, 2) != round(google_percentage, 2):
        msg = "Percentage mismatch for %s: %.2f%% vs %.2f%% (%d days)" % (
            row[0], notrip_percentage * 100, google_percentage, notrip_days)
        if self.check_percentages and country == "US":
          # Don't warn twice.
          print "Warning:", msg
    return percentage

  def GetCountryTotal(self, country, column):
    total = 0.0
    currency = GetCountryCurrency(country)
    for purno, country_data in self.data.iteritems():
      if country in country_data:
        data = country_data[country]
        date = data[self.date_column]
        percentage = self.GetCountryPercentage(data, country)
        usd_value = self.GetCurrencyValue(data[column])
        value = self.converter.ConvertCurrency(usd_value, "USD",
                                               currency, date, "TTM")
        total += value * percentage
    return self.CurrencyValueToString(total, country)

  def PrintEvents(self):
    for purno in self.data:
      event = self.data[purno]
      randomcountry = event.keys()[0]
      randomrow = event[randomcountry]
      print purno, randomrow[0], randomrow[2], randomrow[6]
      for country in event:
        print "  %s: %.2f%%" % (
            country, self.GetCountryPercentage(event[country], country) * 100)

  def GenerateCountryReport(self, country):
    currency = GetCountryCurrency(country)
    columns = self.REPORT_COLUMNS.get(country)
    if not columns:
      columns = self.REPORT_COLUMNS[country[:country.index("_")]]

    report = []
    headings = [description for name, description in columns]
    report.append(headings)

    total = 0.00
    for purno in self.data:
      if country in self.data[purno]:
        row = self.data[purno][country]
        date = row[self.FindDateColumn()]

        fx_rate = self.converter.ConvertCurrency(1, "USD", currency,
                                                 date, "TTM")

        total_days = self.GetTotalDays(row)
        country_days = self.GetCountryDays(row, country, False)
        trip_days = country_days - self.GetCountryDays(row, country, True)
        country_percentage = (country_days - trip_days) / float(total_days)
        taxable = self.GetTotal(row) * country_percentage
        local_taxable = taxable * fx_rate
        total += local_taxable

        values = {
            "_AWARD_DATE": self.GetGrantDate(row[self.FindGrantColumn()]),
            "_FX_RATE": fx_rate,
            "_TOTAL_DAYS": total_days,
            "_COUNTRY_DAYS": country_days,
            "_TRIP_DAYS": trip_days,
            "_TAXABLE": self.CurrencyValueToString(taxable,
                                                   self.STATEMENT_COUNTRY),
            "_LOCAL_TAXABLE": self.CurrencyValueToString(local_taxable,
                                                         country),
        }

        outputrow = []
        for name, description in columns:
          if name.startswith("_"):
            value = values[name]
          else:
            if name.isupper():
              value = row[self.FindColumnByType(name)]
            else:
              value = row[self.FindColumn(name)]
          if isinstance(value, datetime.datetime):
            value = value.strftime("%Y-%m-%d")
          outputrow.append(str(value))
        report.append(outputrow)

    # The last row only has the total.
    total = self.CurrencyValueToString(total, country)
    lastrow = [""] * (len(columns) - 1 ) + [total]
    report.append(lastrow)

    def HtmlTableRow(l):
      return "<tr>" + "".join("<td>%s</td>" % value for value in l) + "</tr>"

    return self.REPORT_TEMPLATE % {
        "country": COUNTRY_NAMES[country],
        "rows": "\n".join(HtmlTableRow(row) for row in report),
        "title": self.REPORT_TITLES[self.name],
    }

  def __str__(self):
    out = "%s = {\n" % self.name
    for purno in self.data:
      out += "    '%s': [\n" % purno
      for row in self.data[purno]:
        out += "        %s,\n" % row
      out += "    ],\n"
    out += "}"
    return out
