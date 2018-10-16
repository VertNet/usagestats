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
__version__ = "InitExtraction.py 2018-10-15T22:47-03:00"

import json
import logging
from google.appengine.ext import ndb
from google.appengine.api import memcache, taskqueue
import webapp2
from models import Period, ReportToProcess, Report
from config import *

class InitExtraction(webapp2.RequestHandler):
    """Initialize the processing of a Period."""
    def post(self):
        """Parse parameters, call initialization function
           and launch searches and downloads extractions.
        """
        # Parse parameters
        err = self.store_parameters()
        if err:
            return

        # Call initialization function
        err = self.initialize_extraction()
        if err:
            return

        # Create task for extracting events
        taskqueue.add(url=URI_GET_EVENTS, queue_name=QUEUENAME)

        # Build response
        resp = {
            "status": "success",
            "message": "Period initialized and extractions enqueued",
            "data": {
                "period": self.period
            }
        }
        self.response.write(json.dumps(resp) + "\n")
        return

    def store_parameters(self):
        """Store and memcache arguments in POST request body."""
        # Store call parameters
        self.period = self.request.get('period', None)
        self.force = self.request.get('force').lower() == 'true'
        self.testing = self.request.get('testing').lower() == 'true'
        self.github_store = self.request.get('github_store').lower() == 'true'
        self.github_issue = self.request.get('github_issue').lower() == 'true'
        self.table_name = self.request.get('table_name', CDB_TABLE)

        # Store in memcache for further reference
        missed = memcache.set_multi({
            # Extraction variables
            "period": self.period,
            "force": self.force,
            "testing": self.testing,
            "github_store": self.github_store,
            "github_issue": self.github_issue,
            "table_name": self.table_name,
            # Process tracking variables
            "searches_extracted": False,
            "downloads_extracted": False,
            "processed_searches": 0,
            "processed_downloads": 0
        }, key_prefix="usagestats_parser_")

        if len(missed) > 0:
            s =  "Version: %s\n" % __version__
            s += "Call parameters for memcache missing: %s " % missed
            logging.warning(s)
        else:
            s =  "Version: %s\n" % __version__
            s += "Call parameters successfully added to memcache"
            logging.info(s)

        return 0

    def initialize_extraction(self, period=None, force=None):
        """Check if Period parameter is valid, if the Period entity already exists
           and create a new Period.
        """
        self.response.headers['Content-Type'] = "application/json"

        # Check that 'period' is provided
        if not self.period:
            s =  "Version: %s\n" % __version__
            s += "Period not found on POST body. Aborting."
            logging.error(s)
            self.error(400)
            resp = {
                "status": "error",
                "message": s
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        # Check that 'period' is valid
        if len(self.period) != 6:
            s =  "Version: %s\n" % __version__
            s += "Malformed period. Should be YYYYMM (e.g., 201603)"
            logging.error(s)
            self.error(400)
            resp = {
                "status": "error",
                "message": s
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        # Get existing period
        period_key = ndb.Key("Period", self.period)
        period_entity = period_key.get()

        # If existing, abort or clear and start from scratch
        if period_entity:
            if self.force is not True:
                s =  "Version: %s\n" % __version__
                s += "Period %s already exists. " % self.period
                s += "Aborting. To override, use 'force=true'."
                logging.error(s)
                resp = {
                    "status": "error",
                    "message": s
                }
                self.response.write(json.dumps(resp) + "\n")
                return 1
            else:
                s =  "Version: %s\n" % __version__
                s += "Period %s already exists. " % self.period
                s += "Overriding."
                logging.warning(s)

                # Delete Reports referencing period
                r = Report.query().filter(Report.reported_period == period_key)
                to_delete = r.fetch(keys_only=True)
                s =  "Version: %s\n" % __version__
                s += "Deleting %d Report entities" % len(to_delete)
                logging.info(s)
                deleted = ndb.delete_multi(to_delete)
                s =  "Version: %s\n" % __version__
                s += "%d Report entities removed" % len(deleted)
                logging.info(s)

                # Delete Period itself
                s =  "Version: %s\n" % __version__
                s += "Deleting Period %s" % period_key
                logging.info(s)
                period_key.delete()
                s =  "Version: %s\n" % __version__
                s += "Period %s deleted" % period_key
                logging.info(s)

        # Create new Period (id=YYYYMM)
        s =  "Version: %s\n" % __version__
        s += "Creating new Period %s" % self.period
        logging.info(s)
        y, m = (int(self.period[:4]), int(self.period[-2:]))
        p = Period(id=self.period)
        p.year = y
        p.month = m
        p.status = 'in progress'
        period_key = p.put()

        # Check
        if period_key:
            s =  "Version: %s\n" % __version__
            s += "New Period %s created successfully" % self.period
            s += "with key %s" % period_key
            logging.info(s)
        else:
            self.error(500)
            s =  "Version: %s\n" % __version__
            s += "Could not create new Period %s" % self.period
            logging.error(s)
            resp = {
                "status": "error",
                "message": s
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        # Clear temporary entities
        keys_to_delete = ReportToProcess.query().fetch(keys_only=True)
        s =  "Version: %s\n" % __version__
        s += "Deleting %d temporal (internal use only) entities" % len(keys_to_delete)
        logging.info(s)
        ndb.delete_multi(keys_to_delete)

        return 0
