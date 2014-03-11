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

__version__ = "0.1"

# Figure out what year it is so we can set flag defaults.
thisyear = datetime.date.today().year
taxyear = thisyear - 1

FLAGS = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
FLAGS.add_argument("--calendar", type=str,
                   default="calendar.csv",
                   help="CSV file listing residence and business trips")
FLAGS.add_argument("--fx", type=str,
                   default="murc_%d.csv" % taxyear,
                   help="CSV file with exchange rates")
FLAGS.add_argument("--grants", type=str,
                   default="grants.csv",
                   help="CSV file with GSU and option stock grants")
FLAGS.add_argument("--statement", type=str,
                   default="google_year_end_stock_statement.csv",
                   help="Google year end stock statement")
FLAGS.add_argument("--check_percentages", type=int,
                   default=1,
                   help="Check CA percentages against Google numbers")
FLAGS = FLAGS.parse_args(sys.argv[1:])


def main():
  converter = currencyconverter.MURCCurrencyConverter(FLAGS.fx)
  test_date = datetime.datetime.strptime("27-Jan-13", "%d-%b-%y")
  assert 4981.35 == round(converter.ConvertCurrency(55, "USD", "JPY",
                                                  test_date, "TTM"), 2)
  print "Read exchange rate data."

  calendar = taxcalendar.TaxCalendar.ReadFromCSV(FLAGS.calendar)
  print "Read location data."
  for year in calendar.GetYears():
    locations = calendar.FindLocationsForYear(year)
    print "  %s: %s" % (year, str(dict(locations)))

  grant_data = stocktable.GrantTable.ReadFromCSV(FLAGS.grants)
  print
  print "Read grant data."

  sales = stocktable.StockTable.ReadFromCSV(FLAGS.statement,
                                            grant_data, converter, calendar)
  all_countries = set()
  for table in sales.values():
    print "Setting check percentages to ", repr(FLAGS.check_percentages)
    table.SetCheckPercentages(FLAGS.check_percentages)
    all_countries.update(table.GetAllCountries())
  print
  print "Read stock data."
  print "  Sections:", sales.keys()
  print "  Countries:", all_countries
  print

  print "Country totals:"
  for section, table in sales.iteritems():
    column = table.FindIncomeColumn()
    print "    %s" % section
    for country in all_countries:
      print "        %5s: %12s" % (country, table.GetCountryTotal(country,
                                                                  column))
    print


#main()
