# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = '@jotegui'
__contributors__ = "Javier Otegui, John Wieczorek"
__copyright__ = "Copyright 2018 vertnet.org"
__version__ = "models.py 2018-12-11T12:55-03:00"
MODELS_VERSION=__version__

from datetime import datetime
from google.appengine.ext import ndb

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

    period = ndb.ComputedProperty(
        lambda self: datetime.strptime(
            "{0}-{1}".format(self.year, self.month),
            "%Y-%m"
        )
    )

    downloads_to_process = ndb.IntegerProperty()
    searches_to_process = ndb.IntegerProperty()
    processed_downloads = ndb.IntegerProperty(default=0)
    processed_searches = ndb.IntegerProperty(default=0)

    # Processing properties sdded to replace memcache
    # Process extraction variables
    period_parameter = ndb.StringProperty()
    force = ndb.BooleanProperty()
    testing = ndb.BooleanProperty()
    github_store = ndb.BooleanProperty()
    github_issue = ndb.BooleanProperty()
    table_name = ndb.StringProperty()
    # Process tracking variables
    searches_extracted = ndb.BooleanProperty()
    downloads_extracted = ndb.BooleanProperty()
    processed_searches = ndb.IntegerProperty()
    processed_downloads = ndb.IntegerProperty()

class StatsRun(ndb.Model):
    """Holds the period information for the stat processing run.
Key name: VNStats
Ancestor: None
"""
    period = ndb.StringProperty()
    gbifdatasetid = ndb.StringProperty()

class CartoEntry(ndb.Expando):
    """Identifies an entry of the query_log_master table in Carto.
Key: cartodb_id
"""
    pass

class CartoDownloadEntry(CartoEntry):
    pass

class CartoSearchEntry(CartoEntry):
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
    stored = ndb.BooleanProperty()
    issue_sent = ndb.BooleanProperty()
    done = ndb.ComputedProperty(lambda self:
                                # self.downloads.status == 'done' and
                                # self.searches.status == 'done' and
                                self.issue_sent is True and
                                self.stored is True)

class ReportToProcess(ndb.Model):
    """Identifies a Report to be processed.
This helper class is called by 'GetEvents' to temporarily store some basic data
on all the reports that need to be processed.
"""
    t = ndb.StringProperty(required=True)
    gbifdatasetid = ndb.StringProperty(required=True)
    resource = ndb.JsonProperty(required=True)
