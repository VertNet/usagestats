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
__version__ = "InitExtraction.py 2018-12-10T17:43-03:00"

import json
import logging
from google.appengine.ext import ndb
from google.appengine.api import taskqueue
import webapp2
from models import Period, ReportToProcess, Report, StatsRun
from config import *

class InitExtraction(webapp2.RequestHandler):
    """Initialize the processing of a Period."""
    def post(self):
        """Parse parameters, call initialization function
           and launch searches and downloads extractions.
        """
        # Parse parameters
        self.store_parameters()

        # Call initialization function
        err = self.initialize_extraction()
        if err:
            return

        # Persist parameters in Period entity
        err = self.persist_parameters()
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
        """Store arguments from POST request body."""
        # Store call parameters
        self.period = self.request.get('period', None)
        self.force = self.request.get('force').lower() == 'true'
        self.testing = self.request.get('testing').lower() == 'true'
        self.github_store = self.request.get('github_store').lower() == 'true'
        self.github_issue = self.request.get('github_issue').lower() == 'true'
        # Get default table name, CDB_TABLE, from config.py
        self.table_name = self.request.get('table_name', CDB_TABLE)
        return 0

    def persist_parameters(self):
        """Store parameters as Period entity properties."""
        # Store call parameters
        # Get period from StatsRun entity
        run_key = ndb.Key("StatsRun", 5759180434571264)
        run_entity = run_key.get()
        if run_entity is None:
            s =  "Version: %s\n" % __version__
            s += "Could not create StatsRun entity for period %s" % self.period
            logging.error(s)
            self.error(500)
            resp = {
                "status": "error",
                "message": s,
                "data": {
                "period": self.period,
                }
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        run_entity.period = self.period
        k = run_entity.put()
        if k is None:
            s =  "Version: %s\n" % __version__
            s += "Could not create StatsRun entity for period %s" % self.period
            logging.error(s)
            self.error(500)
            resp = {
                "status": "error",
                "message": s,
                "data": {
                    "period": self.period,
                }
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        # Get Period entity
        period_key = ndb.Key("Period", self.period)
        period_entity = period_key.get()

        # Store in Period entity for further reference
        period_entity.period_parameter = self.period
        period_entity.force = self.force
        period_entity.testing = self.testing
        period_entity.github_store = self.github_store
        period_entity.github_issue = self.github_issue
        period_entity.table_name = self.table_name
        period_entity.searches_extracted = False
        period_entity.downloads_extracted = False
        period_entity.processed_searches = 0
        period_entity.processed_downloads = 0

        # Store updated period data
        k = period_entity.put()
        if k != period_key:
            s =  "Version: %s\n" % __version__
            s += "Could not update processing properties in period %s" % self.period
            logging.error(s)
            self.error(500)
            resp = {
                "status": "error",
                "message": s,
                "data": {
                    "period": self.period,
                }
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        s =  "Version: %s\n" % __version__
        s += "Arguments from POST:"
        for arg in self.request.arguments():
            s += '\n%s:%s' % (arg, self.request.get(arg))
        s += "Processing properties in Period entity:"
        s += "\n%s" % period_entity.period_parameter
        s += "\n%s" % period_entity.force
        s += "\n%s" % period_entity.testing
        s += "\n%s" % period_entity.github_store
        s += "\n%s" % period_entity.github_issue
        s += "\n%s" % period_entity.table_name
        s += "\n%s" % period_entity.searches_extracted
        s += "\n%s" % period_entity.downloads_extracted
        s += "\n%s" % period_entity.processed_searches
        s += "\n%s" % period_entity.processed_downloads
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
