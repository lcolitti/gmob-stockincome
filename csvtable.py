# coding=UTF-8

import csv

class CSVTable(object):

  def __init__(self, name, headings):
    self.name = name
    self.headings = headings

  def CheckRow(self, row):
    if len(row) != len(self.headings):
      raise ValueError("Invalid row: %s.\nHeadings: %s" % (row, self.headings))

  def AddRow(self, row):
    raise NotImplementedError

  def __getitem__(self, i):
    return self.data[i]    


def CSVReader(filename):
  return csv.reader(open(filename, "r"), delimiter=",", quotechar='"',
                    strict=True)


def ReadMultitableCSV(filename, constructor):
  """Reads a CSV file that contains multiple tables.

  The file is divided into tables separated by lines with no data. A non-empty
  first column contains a table name and starts a new table; subsequent lines in
  the same table have an empty first column. Tables are separated by blank
  lines. For example:

  Table name 1, Column heading 1, Column heading 2, ...
  , Row 1 col 1, Row 1 col 2, ...
  , Row 2 col 1, Row 2 col 2, ...
  ...

  Table name 2, Column heading 1, Column heading 2, ...
  , Row 1 col 1, Row 1 col 2, ...
  , Row 2 col 1, Row 2 col 2, ...  
  ...

  Table objects are created using the specified constructor function, which
  takes two arguments:
    name: A string, the name of the table.
    headings: A list of strings, the section's table headings.

  The created object must be a subclass of CSVTable.

  Args:
    filename: A string, the filename to read.
    constructor: A function that creates a table object, described above.

  Returns:
    A dict mapping table names to tables.
  """
  tables = {}

  reader = CSVReader(filename)
  for row in reader:
    if not len(row):
      # Empty line. Skip.
      continue
    name = row[0]
    data = row[1:]
    if name:
      table = constructor(name, data)
      tables[name] = table
    else:
      table.AddRow(data)

  return tables


def ReadCSVTables(tablenames, filenames, constructors):
  """Reads data from multiple CSV files.

  Reads the specified CSV files, and for each one creates a table.  Table
  objects are created using the specified constructor functions, which
  take two arguments:
    name: A string, the name of the table.
    headings: A list of strings, the section's table headings.

  The name is taken from the tablenames list.

  The created objects must be a subclass of CSVTable.

  Args:
    tablenames: A list of strings, the table names.
    filename: A list of strings, the filenames to read.
    constructor: A list of functions that create a table object, as above.

  Returns:
    A dict mapping table names to tables.
  """
  tables = {}

  for name, filename, constructor in zip(tablenames, filenames, constructors):
    reader = CSVReader(filename)
    headings = reader.next()

    table = constructor(name, headings)
    if name in tables:
      raise ValueError("Table name %s already exists" % name)
    tables[name] = table

    for row in reader:
      table.AddRow(row)

  return tables
