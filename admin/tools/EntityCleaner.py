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
__version__ = "EntityCleaner.py 2018-10-09T16:09-03:00"
ENTITYCLEANER_VERSION=__version__

from google.appengine.ext import ndb
import webapp2
from config import *

class EntityCleaner(webapp2.RequestHandler):
    def get(self):
        pass
