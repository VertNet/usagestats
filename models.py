from datetime import datetime
from google.appengine.ext import ndb

__author__ = 'jotegui'


class Dataset(ndb.Model):
    """Identifies a Dataset.
Key name: GBIFDATASETID
Ancestor: None
"""
    # GBIF IDs
    gbifdatasetid = ndb.StringProperty()
    gbifpublisherid = ndb.StringProperty()
    # Old-style IDs
    url = ndb.StringProperty()
    icode = ndb.StringProperty()
    ccode = ndb.ComputedProperty(lambda self: self.url.split("=")[-1])
    # GitHub IDs
    orgname = ndb.StringProperty()
    github_orgname = ndb.StringProperty()
    github_reponame = ndb.StringProperty()
    # Other stuff
    source_url = ndb.StringProperty()


class Period(ndb.Model):
    """Identifies an extraction.
Key name: YYYYMM
Ancestor: None
"""
    year = ndb.IntegerProperty()
    month = ndb.IntegerProperty()
    downloads_in_period = ndb.IntegerProperty()
    records_downloaded_in_period = ndb.IntegerProperty()
    searches_in_period = ndb.IntegerProperty()
    records_searched_in_period = ndb.IntegerProperty()
    status = ndb.StringProperty(choices=['done', 'in progress', 'failed'])

    period = ndb.ComputedProperty(lambda self: datetime.strptime("{0}-{1}".format(self.year, self.month), "%Y-%m"))

    downloads_to_process = ndb.IntegerProperty()
    searches_to_process = ndb.IntegerProperty()
    processed_downloads = ndb.IntegerProperty(default=0)
    processed_searches = ndb.IntegerProperty(default=0)


class CartodbEntry(ndb.Expando):
    """Identifies an entry of the query_log_master table in CartoDB.
Key: cartodb_id
"""
    pass


class CartodbDownloadEntry(CartodbEntry):
    pass


class CartodbSearchEntry(CartodbEntry):
    pass


class QueryTerms(ndb.Model):
    """
Key name: query_terms
Ancestor: Report
"""
    query_terms = ndb.StringProperty()
    records = ndb.IntegerProperty(default=0)
    times = ndb.IntegerProperty(default=0)


class QueryCountry(ndb.Model):
    """
Key name: query_country
Ancestor: Report
"""
    query_country = ndb.StringProperty()
    times = ndb.IntegerProperty(default=0)


class QueryDate(ndb.Model):
    """
Key name: query_date
Ancestor: Report
"""
    query_date = ndb.DateProperty()
    times = ndb.IntegerProperty(default=0)


class PastData(ndb.Model):
    searches = ndb.IntegerProperty(default=0)
    searched_records = ndb.IntegerProperty(default=0)
    downloads = ndb.IntegerProperty(default=0)
    downloaded_records = ndb.IntegerProperty(default=0)
    query_terms = ndb.StructuredProperty(QueryTerms, repeated=True)
    query_countries = ndb.StructuredProperty(QueryCountry, repeated=True)
    query_dates = ndb.StructuredProperty(QueryDate, repeated=True)


class YearData(PastData):
    pass


class HistoryData(PastData):
    pass


class Download(ndb.Model):
    events = ndb.IntegerProperty(default=0)
    records = ndb.IntegerProperty(default=0)
    # unique = ndb.IntegerProperty(default=0)
    query_terms = ndb.StructuredProperty(QueryTerms, repeated=True)
    query_countries = ndb.StructuredProperty(QueryCountry, repeated=True)
    query_dates = ndb.StructuredProperty(QueryDate, repeated=True)
    # status = ndb.StringProperty(choices=['done', 'in progress', 'failed'])


class Search(ndb.Model):
    events = ndb.IntegerProperty(default=0)
    records = ndb.IntegerProperty(default=0)
    query_terms = ndb.StructuredProperty(QueryTerms, repeated=True)
    query_countries = ndb.StructuredProperty(QueryCountry, repeated=True)
    query_dates = ndb.StructuredProperty(QueryDate, repeated=True)
    # status = ndb.StringProperty(choices=['done', 'in progress', 'failed'])


class Report(ndb.Model):
    """Identifies a Report.
Key name: concatenation of period and gbifdatasetid: YYYYMM|0000-0000-0000-0000
Ancestor: Period
"""
    created = ndb.DateProperty(required=True)
    # url = ndb.StringProperty()
    sha = ndb.StringProperty(default="")
    reported_period = ndb.KeyProperty(kind=Period, required=True)
    reported_resource = ndb.KeyProperty(kind=Dataset, required=True)
    searches = ndb.StructuredProperty(Search)
    downloads = ndb.StructuredProperty(Download, default=Download())
    year_data = ndb.StructuredProperty(YearData)
    history_data = ndb.StructuredProperty(HistoryData)
    issue_sent = ndb.BooleanProperty()
    done = ndb.ComputedProperty(lambda self:
                                # self.downloads.status == 'done' and
                                # self.searches.status == 'done' and
                                self.issue_sent is True)
