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
__version__ = "DatasetsSetup.py 2018-10-09T15:39-03:00"
DATASETSSETUP_VERSION=__version__

import json
from google.appengine.ext import ndb
from google.appengine.api import urlfetch
import webapp2
from models import Dataset
from util import carto_query

class DatasetsSetup(webapp2.RequestHandler):
    """Populates the datastore with Dataset objects."""
    def post(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.headers['Content-Type'] = 'application/json'

        q = "select gbifdatasetid, icode, orgname, github_orgname, " \
            "source_url, github_reponame, url, gbifpublisherid " \
            "from resource_staging " \
            "where ipt=true and networks like '%VertNet%'"
        resources = carto_query(q)

        ds = []
        for resource in resources:
            ds.append(Dataset(id=resource['gbifdatasetid'], **resource))

        keys = ndb.put_multi(ds)

        result = {
            "datasets processed": len(keys),
        }

        self.response.write(json.dumps(result))
        return
