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
__version__ = "PeriodStatus.py 2018-10-15T22:42-03:00"

import json
from google.appengine.api.modules import modules
from google.appengine.ext import ndb
import jinja2
from models import Period, Dataset, Report, CartoDownloadEntry
from util import *
import webapp2

_HOSTNAME = modules.get_hostname(module="tools-usagestats")
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class PeriodStatus(webapp2.RequestHandler):
    def get(self, period):
        period_key = ndb.Key("Period", period)
        entity = period_key.get()
        if entity:
            status = entity.status
        else:
            status = "not done"
        getdownloadslist = CartoDownloadEntry.query(ancestor=period_key).count() > 0

        resp = {
            "Requested period": period,
            "Status of report": status,
        }

        if entity.status == "in progress":
            resp['Extraction status'] = [
                {"Downloads to process": entity.downloads_to_process},
                {"Downloads processed": entity.processed_downloads},
                {"Searches to process": entity.searches_to_process},
                {"Searches processed": entity.processed_searches}
            ]
        elif entity.status == 'done':
            resp['Period data'] = [
                {"Download events": entity.downloads_in_period},
                {"Records downloaded": entity.records_downloaded_in_period},
                {"Search events": entity.searches_in_period},
                {"Records searched": entity.records_searched_in_period},
                {"Distinct datasets in all downloads": entity.downloads_to_process},
                {"Distinct datasets in all searches": entity.searches_to_process}
            ]

        self.response.headers["content-type"] = "application/json"
        self.response.write(json.dumps(resp))


# class FutureChecker(webapp2.RequestHandler):
#     def post(self):
#         futures = self.request.get('futures')

#         template = JINJA_ENVIRONMENT.get_template('futures.html')
#         self.response.headers["content-type"] = "text/plain"
#         self.response.write(template.render(
#             futures=futures
#         ))

# class PeriodListHandler(webapp2.RequestHandler):
#     def get(self):
#         urlfetch.set_default_fetch_deadline(60)

#         # Get all reports on GitHub
#         reports_call = urlfetch.fetch(
#             url='/'.join([ghb_url, "repos", ghb_org, ghb_rep, "git",
#                           "trees", tree_sha]),
#             headers=ghb_headers,
#             method=urlfetch.GET
#         )
#         reports = json.loads(reports_call.content)['tree']

#         periods = sorted(list(set(["/".join(x['path'].split(".")[0]\
#                                   .split("_")[-2:]) for x in reports])))

#         resp = {"Processed periods": periods}

#         self.response.headers['Content-type'] = "application/json"
#         self.response.write(json.dumps(resp))
