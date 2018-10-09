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
__version__ = "Status.py 2018-10-09T15:50-03:00"
STATUS_VERSION=__version__

import json
from google.appengine.api.modules import modules
from google.appengine.ext import ndb
import jinja2
from models import Period, Dataset, Report, CartoDownloadEntry
from util import *
import webapp2

_HOSTNAME = modules.get_hostname(module="tools-usagestats")
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                   'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Status(webapp2.RequestHandler):
    def get(self):

        # Check if datasets are loaded in datastore

        # Items in datastore
        d = Dataset.query().count()
        # Items in Carto
        q = "select count(*) as c from resource_staging" + \
            " where ipt is true and networks like '%VertNet%';"
        c = carto_query(q)[0]['c']

        # Number of reports stored in the datastore
        num_reports = Report.query().count()

        periods = Period.query()
        num_periods = periods.count()

        periods_done = Period.query(Period.status == "done")
        num_periods_done = periods_done.count()

        periods_progress = Period.query(Period.status == "in progress")
        num_periods_progress = periods_progress.count()

        periods_failed = Period.query(Period.status == "failed")
        num_periods_failed = periods_failed.count()

        resp = {
            "Datastore integrity": [
                {"Datasets in Carto": c},
                {"Datasets in the Datastore": d}
            ],
            "Report periods": [
                {"Stored periods": num_periods},
                {"Stored reports": num_reports},
                {"Periods completed": num_periods_done},
                {"Periods in progress": num_periods_progress},
                {"Periods failed": num_periods_failed},
            ]
        }

        if c != d or c == 0:
            dataset_setup_url = "http://%s/setup_datasets" % _HOSTNAME
            resp["Datastore integrity"].append({"URL for dataset setup": dataset_setup_url})
        if num_periods > 0:
            links_to_periods = ["http://%s/status/period/%s" % (_HOSTNAME, x.key.id()) for x in periods.fetch()]
            resp["Report periods"].append({"Links to periods": links_to_periods})
        if num_periods_done > 0:
            resp['Report periods'].append({'List of periods done': [x.period.strftime("%Y-%m") for x in periods_done.fetch()]})
        if num_periods_progress > 0:
            resp['Report periods'].append({'List of periods in progress': [x.period.strftime("%Y-%m") for x in periods_progress.fetch()]})
        if num_periods_failed > 0:
            resp['Report periods'].append({'List of periods failed': [x.period.strftime("%Y-%m") for x in periods_failed.fetch()]})

        self.response.headers['content-type'] = "application/json"
        self.response.write(json.dumps(resp))
