#!/usr/bin/python

"""Find employment income from Google shares in various countries.

Attempts to calculate employment income from GSUs and options based on
residence, business trips, and foreign exchange rates.

USE AT YOUR OWN RISK.
GET TAX ADVICE FROM SOMEONE WHO ACTUALLY KNOWS WHAT THEY'RE DOING.
"""

import argparse
import datetime
import sys

import stocktable
import taxcalendar
import currencyconverter

__version__ = "0.2"

# Figure out what year it is so we can set flag defaults.
thisyear = datetime.date.today().year
defaultyear = thisyear - 1

FLAGS = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
FLAGS.add_argument("--calendar", type=str,
                   default="calendar.csv",
                   help="CSV file listing residence and business trips")
FLAGS.add_argument("--grants", type=str,
                   default="grants.csv",
                   help="CSV file with GSU and option stock grants")
FLAGS.add_argument("--check_percentages", type=int,
                   default=0,
                   help="Check US / US_CA percentages against Google numbers")
FLAGS.add_argument("--year", type=int, default=defaultyear, help="Tax year")
FLAGS.add_argument("--fx", type=str,
                   default=None,
                   help="CSV file with exchange rates, default murc_<year>.csv")
FLAGS = FLAGS.parse_args(sys.argv[1:])


def main():
  converter = currencyconverter.MURCCurrencyConverter(FLAGS.year, FLAGS.fx)
  print "Read exchange rate data."

  calendar = taxcalendar.TaxCalendar.ReadFromCSV(FLAGS.calendar)
  print "Read location data."
  for year in calendar.GetYears():
    locations = calendar.FindLocationsForYear(year)
    print "  %s: %s" % (year, str(dict(locations)))

  grant_data = stocktable.GrantTable.ReadFromCSV(FLAGS.grants)
  print
  print "Read grant data."

  sales = stocktable.StockTable.ReadFromCSV(FLAGS.year, grant_data,
                                            converter, calendar)
  all_countries = set()
  for table in sales.values():
    table.SetCheckPercentages(int(FLAGS.check_percentages))
    all_countries.update(table.GetAllCountries())
  print
  print "Read stock data."
  print "  Sections:", sales.keys()
  print "  Countries:", all_countries
  print

  GSUS = sales["GSUS"]
  #assert 0.00 == sales["GSUS"].GetCountryPercentage(GSUS["A10751504"]["US"], "US")

  print "Country totals:"
  for section, table in sales.iteritems():
    column = table.FindTotalColumn()
    print "    %s" % section
    for country in all_countries:
      print "        %5s: %12s" % (country, table.GetCountryTotal(country,
                                                                  column))
    print

  for country in all_countries:
    for section, table in sales.iteritems():
      report = table.GenerateCountryReport(country)
      filename = "stockincome.%s.%s.html" % (section, country)
      open(filename, "w").write(report)
      print "Wrote report on %s for %s to %s" % (section, country, filename)

#main()
