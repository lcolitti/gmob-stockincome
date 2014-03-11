#!/usr/bin/python
# coding=UTF-8

import csv
import collections
import datetime
import re

class MURCCurrencyConverter(object):

  BASE_CURRENCY = "JPY"
  DATE_FORMAT = "%m/%d/%Y"  # 1/27/2013
  RATES = ["TTS", "TTB", "TTM"]

  def __init__(self, filename):

    # Dictionary of currency values indexed by currency name and date.
    self.values = collections.OrderedDict()

    reader = csv.reader(open(filename, "r"), delimiter=",", quotechar='"')

    # Read headings.
    # 2013年,,米ドル（USD）,,,ユーロ(EUR),,,カナダ・ドル（CAD）,,,...
    headings = reader.next()
    self.year = int(headings[0][:4])
    if self.year < 2000 or self.year > 2030:
      raise ValueError("Year %d doesn't look right" % self.year)

    # Find out which currencies are supported.
    for column in xrange(2, len(headings), 3):
      value = headings[column].strip()
      # Some are normal parentheses, some are full-width. Accept both.
      bra = "[(（]"
      ket = "[）)]"
      currency_re = re.compile(bra + "([A-Z][A-Z][A-Z])" + ket)
      currency = currency_re.search(value).group(1)
      self.values[currency] = collections.OrderedDict()

    if "USD" not in self.values:
      raise ValueError("Need at least USD conversion")

    numdates = 0
    # Keep track of the last rate, for weekends.
    lastrates = {}
    for row in reader:
      try:
        date = datetime.datetime.strptime(row[0], self.DATE_FORMAT)
        numdates += 1
      except ValueError:
        continue

      for i, currency in enumerate(self.values.keys()):
        rates = []
        for j, rate in enumerate(self.RATES):
          column = 2 + 3 * i + j
          value = row[column].strip()
          if value:
            rates.append(float(value))

        if len(rates) == len(self.RATES):
          lastrates[currency] = rates
        elif currency in lastrates:
          rates = lastrates[currency]
        else:
          # No data. Beginning of the year?
          pass

        #if currency == "USD": print date, rates
        self.values[currency][date] = rates

    if numdates not in (365, 366):
      raise ValueError("Invalid number of FX dates")

  def GetRate(self, currency, date, rate):
    rate_index = self.RATES.index(rate)
    if rate_index == -1:
      raise NotImplementedError("Unknown rate type %s" % rate)
    try:
      return self.values[currency][date][rate_index]
    except KeyError:
      raise KeyError("No exchange rate data for %s rate from %s to %s on %s" %
                     (rate, currency, self.BASE_CURRENCY, date))

  def ConvertCurrency(self, value, from_currency, to_currency, date, rate):

    if from_currency == to_currency:
      return value

    def CheckHasCurrency(currency):
      if currency not in self.values.keys() + [self.BASE_CURRENCY]:
        raise NotImplementedError("Unknown currency %s" % from_currency)

    CheckHasCurrency(from_currency)
    CheckHasCurrency(to_currency)


    # Convert from from_currency to our base currency.
    if from_currency == self.BASE_CURRENCY:
      base_value = value
    else:
      base_value = value * self.GetRate(from_currency, date, rate)
    # Convert from our base currency to to_currency.
    if to_currency == self.BASE_CURRENCY:
      return base_value
    else:
      return base_value / self.GetRate(to_currency, date, rate)
