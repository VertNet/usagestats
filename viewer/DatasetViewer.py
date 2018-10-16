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
__version__ = "DatasetViewer.py 2018-10-15T23:17-03:00"

from google.appengine.ext import ndb
import webapp2
from models import Report
from util import *
from jinjafilters import *

class DatasetViewer(webapp2.RequestHandler):
    def get(self, gbifdatasetid):

        dataset_key = ndb.Key("Dataset", gbifdatasetid)

        query = Report.query(Report.reported_resource == dataset_key)
        query = query.order(-Report.reported_period)
        report_keys = query.fetch(keys_only=True)

        period_list = [
            {
                "text": x.id().split("|")[0][:4]+"-"+x.id().split("|")[0][4:],
                "url": x.id().split("|")[0]
            } for x in report_keys]

        template = JINJA_ENVIRONMENT.get_template('dataset.html')
        self.response.write(template.render(
            dataset=dataset_key.get(),
            period_list=period_list,
            periods=len(period_list)
        ))
