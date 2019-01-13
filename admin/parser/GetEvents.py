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
__version__ = "GetEvents.py 2018-12-11T13:58-03:00"

import json
import logging
from datetime import datetime, timedelta
from google.appengine.ext import ndb
from google.appengine.api import taskqueue
import webapp2
from models import ReportToProcess, StatsRun
from util import ApiQueryMaxRetriesExceededError
from util import add_time_limit, carto_query, geonames_query
from config import *

class GetEvents(webapp2.RequestHandler):
    """Download and prepare log events from logging tables."""
    def post(self):

        # Create instance variable to track if parameters came from a direct request
        # Or if they came through Period entity
        self.params_from_request = None
        params = None

        s =  "Version: %s\n" % __version__
        s += "Arguments from POST:"
        for arg in self.request.arguments():
            s += '\n%s:%s' % (arg, self.request.get(arg))
        logging.info(s)

        # Try to get period from the request in case GetEvents was called directly
        self.period = self.request.get("period", None)

        # If real period not in request, try to get parameters from StatsRun entity 
        # in case GetEvents was called from a previous task.
        if self.period is None or len(self.period)==0:
            run_key = ndb.Key("StatsRun", 5759180434571264)
            run_entity = run_key.get()
            self.period = run_entity.period
            self.params_from_request = False
            s =  "Version: %s\n" % __version__
            s += "Period %s determined from StatsRun entity: %s" % (self.period, params)
            logging.info(s)
        else:
            self.params_from_request = True
            s =  "Version: %s\n" % __version__
            s += "Period %s determined from request: %s" % (self.period, self.request)
            logging.info(s)

        if self.period is None or len(self.period)==0:
            self.error(400)
            resp = {
                "status": "error",
                "message": "Period parameter was not provided."
            }
            s =  "Version: %s\n" % __version__
            s += "%s" % resp
            logging.error(s)
            self.response.write(json.dumps(resp)+"\n")
            return

        # If Period not already stored, halt
        period_key = ndb.Key("Period", self.period)
        period_entity = period_key.get()
        if not period_entity:
            self.error(400)
            resp = {
                "status": "error",
                "message": "Provided period does not exist in datastore",
                "data": {
                    "period": self.period
                }
            }
            logging.error(resp)
            self.response.write(json.dumps(resp)+"\n")
            return

        # Get the remaining parameters based on the parameter source
        if self.params_from_request == True: 
            # Get parameters from request

            # 'table_name' parameter
            try:
                self.table_name = self.request.get('table_name')
                if self.table_name is None or len(self.table_name)==0:
                    self.table_name = CDB_TABLE
            except KeyError:
                # Table name not provided, use default
                self.table_name = CDB_TABLE

            # 'downloads_extracted' parameter
            try:
                self.downloads_extracted = self.request.get('downloads_extracted').\
                    lower() == 'true'
            except Exception:
                s =  "Version: %s\n" % __version__
                s += "Aborting. "
                s += "Unable to extract 'downloads_extracted' from request: %s" % request
                logging.error(s)
                return

            # 'searches_extracted' parameter
            try:
                self.searches_extracted = self.request.get('searches_extracted').\
                    lower() == 'true'
            except KeyError:
                s =  "Version: %s\n" % __version__
                s += "Aborting. "
                s += "Unable to extract 'searches_extracted' from request: %s" % request
                logging.error(s)
                return
        else:
            # Get parameters from Period entity

            # 'table_name' parameter
            try:
                self.table_name = period_entity.table_name
                if self.table_name is None or len(self.table_name)==0:
                    self.table_name = CDB_TABLE
            except KeyError:
                # default value for 'table_name' if not provided is None
                self.table_name = CDB_TABLE

            # 'downloads_extracted' parameter
            try:
                self.downloads_extracted = period_entity.downloads_extracted
            except Exception:
                s =  "Version: %s\n" % __version__
                s += "Aborting. "
                s += "Unable to extract 'downloads_extracted' from Period"
                logging.error(s)
                return

            # 'searches_extracted' parameter
            try:
                self.searches_extracted = period_entity.searches_extracted
            except Exception:
                s =  "Version: %s\n" % __version__
                s += "Aborting. "
                s += "Unable to extract 'searches_extracted' from Period"
                logging.error(s)
                return

        s =  "Version: %s\n" % __version__
        s += "Using %s as data table" % self.table_name
        logging.info(s)

        # Start with downloads
        if self.downloads_extracted == False:
            self.t = "download"
        # and continue with searches
        elif self.searches_extracted == False:
            self.t = "search"
        # if both are True, downloads and searches were both extracted...
        else:
            # ... call 'process_events' and move on
            taskqueue.add(url=URI_PROCESS_EVENTS, queue_name=QUEUENAME)
            return

        # Get events
        s =  "Version: %s\n" % __version__
        s += "Getting events"
        logging.info(s)
        err = self.get_events()
        if err:
            s =  "Version: %s\n" % __version__
            s += "Error from get_events(): %s" % err
            logging.error(s)
            return

        # Parse events
        s =  "Version: %s\n" % __version__
        s += "Parsing events"
        logging.info(s)
        err = self.parse_events()
        if err:
            s =  "Version: %s\n" % __version__
            s += "Error from parse_events(): %s" % err
            logging.error(s)
            return

        # Update Period counts
        s =  "Version: %s\n" % __version__
        s += "Updating Period counts"
        logging.info(s)
        err = self.update_period_counts()
        if err:
            s =  "Version: %s\n" % __version__
            s += "Error from update_period_counts(): %s" % err
            logging.error(s)
            return

        r = []
        for resource in self.resources:
            params = {
                "t": self.t,
                "gbifdatasetid": resource,
                "resource": self.resources[resource]
            }
            r.append(ReportToProcess(**params))

        # Store temporary entities
        s =  "Version: %s\n" % __version__
        s += "Putting %d entities" % len(r)
        logging.info(s)
        sr = ndb.put_multi(r)

        # Check
        if len(sr) != len(r):
            s =  "Version: %s\n" % __version__
            s += "Not all resources were put to process."
            logging.error(s)
            self.error(500)
            resp = {
                "status": "error",
                "message": s,
                "data": {
                    "period": self.period,
                    "t": self.t,
                    "resources": len(r),
                    "to_process": len(sr)
                }
            }
            self.response.write(json.dumps(resp) + "\n")
            return

        # Build response
        resp = {
            "status": "success",
            "message": "All %s events downloaded and parsed" % self.t,
            "data": {
                "period": self.period,
                "event_type": self.t,
                "event_number": len(self.data),
                "resources_to_process": len(self.resources)
            }
        }
        self.response.write(json.dumps(resp) + "\n")

        # Update Period entity with stat information
        if self.t == "search":
            period_entity.searches_extracted=True
        else:
            period_entity.downloads_extracted=True

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
        
        # If both downloads and searches have been extracted, end now
        period_entity = period_key.get()
        if period_entity.searches_extracted is True and\
           period_entity.downloads_extracted is True:
            # Call 'process_events'
            s =  "Version: %s\n" % __version__
            s += "All searches and downloads extracted"
            logging.info(s)
            taskqueue.add(url=URI_PROCESS_EVENTS, queue_name=QUEUENAME)
        else:
            taskqueue.add(url=URI_GET_EVENTS, queue_name=QUEUENAME)
        return

    def get_events(self):
        """Build query and extract records."""

        # Extract Carto data, base query
        s =  "Version: %s\n" % __version__
        s += "Building %s query" % self.t
        logging.info(s)
        if self.t == 'download':
            # Line #6 of SQL is to avoid too large queries
            query = "SELECT cartodb_id, lat, lon, created_at, " \
                    "query AS query_terms, response_records, " \
                    "results_by_resource " \
                    "FROM %s " \
                    "WHERE type='download' "\
                    "AND octet_length(query)<=1500 " \
                    "AND download IS NOT NULL " \
                    "AND download !=''" % self.table_name
        else:
            # Line #6 of SQL is to avoid too large queries
            query = "SELECT cartodb_id, lat, lon, created_at, " \
                    "query AS query_terms, response_records, " \
                    "results_by_resource " \
                    "FROM %s " \
                    "WHERE left(type, 5)='query' " \
                    "AND octet_length(query)<=1500 " \
                    "AND results_by_resource IS NOT NULL " \
                    "AND results_by_resource != '{}' " \
                    "AND results_by_resource !=''" % self.table_name

        # Just production portal downloads
        query += " AND client='portal-prod'"

        # Only restrict time if using default table
        if self.table_name == CDB_TABLE:
            queried_date = datetime(
                int(self.period[:4]),
                int(self.period[-2:]),
                1
            )
            queried_date += timedelta(days=32)
            query = add_time_limit(query=query, today=queried_date)

        s =  "Version: %s\n" % __version__
        s += "Executing query:\n%s" % query
        logging.info(s)
        try:
            data = carto_query(query)
        except ApiQueryMaxRetriesExceededError:
            self.error(504)
            resp = {
                "status": "error",
                "message": "Could not retrieve data from Carto",
                "data": {
                    "period": self.period,
                    "event_type": self.t
                }
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        # Store 'data' in class property
        self.data = data

        # Finish method
        s =  "Version: %s\n" % __version__
        s += "Extracted %d %s events" % (len(data), self.t)
        logging.info(s)
        return 0

    def parse_events(self):
        """Preformat some special fields and redistribute records into resources."""

        # Format according to the Model classes
        s =  "Version: %s\n" % __version__
        s += "Formatting results"
        logging.info(s)
        resources = {}

        for event in self.data:

            # Preformat some fields
            event_created = datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            # Keep just YMD
            event_created = event_created.strftime('%Y-%m-%d')
            event_results = json.loads(event['results_by_resource'])
            event_country = geonames_query(event['lat'], event['lon'])
            event_terms = event['query_terms']

            for resource in event_results:

                # Initialize resource if not existing
                if resource not in resources:
                    resources[resource] = {
                        'records': 0,
                        'query_countries': {},
                        'query_dates': {},
                        'query_terms': {}
                    }

                # Add records
                resources[resource]['records'] += event_results[resource]

                # Add query country
                if event_country not in resources[resource]['query_countries']:
                    resources[resource]['query_countries'][event_country] = {
                        'query_country': event_country,
                        'times': 1
                    }
                else:
                    resources[resource]['query_countries'][event_country]['times'] += 1

                # Add query date
                if event_created not in resources[resource]['query_dates']:
                    resources[resource]['query_dates'][event_created] = {
                        'query_date': event_created,
                        'times': 1
                    }
                else:
                    resources[resource]['query_dates'][event_created]['times'] += 1

                # Add query terms
                if event_terms not in resources[resource]['query_terms']:
                    resources[resource]['query_terms'][event_terms] = {
                        'query_terms': event_terms,
                        'times': 1,
                        'records': event_results[resource]
                    }
                else:
                    et = resources[resource]['query_terms'][event_terms]
                    et['times'] += 1
                    et['records'] += event_results[resource]
#                     resources[resource]['query_terms'][event_terms]['times'] += 1
#                     resources[resource]['query_terms'][event_terms]['records'] \
#                        += event_results[resource]

        # Store 'resources' in class property
        self.resources = resources

        # Finish method
        s =  "Version: %s\n" % __version__
        s += "Created %d resources" % len(self.resources)
        logging.info(s)
        return 0

    def update_period_counts(self):
        """Add searches and downloads counts to Period entity."""

        # Get Period entity
        period_key = ndb.Key("Period", self.period)
        period_entity = period_key.get()

        # Update (downloads|searches)_in_period and
        # (downloads|searches)_to_process in Period
        if self.t == 'download':
            period_entity.downloads_in_period = len(self.data)
            period_entity.records_downloaded_in_period = \
                sum([int(x['response_records']) for x in self.data])
            period_entity.downloads_to_process = len(self.resources)
        elif self.t == 'search':
            period_entity.searches_in_period = len(self.data)
            period_entity.records_searched_in_period = \
                sum([int(x['response_records']) for x in self.data])
            period_entity.searches_to_process = len(self.resources)

        # Store updated period data
        k = period_entity.put()
        if k != period_key:
            s =  "Version: %s\n" % __version__
            s += "Could not update %s counts in period" % self.t
            logging.error(s)
            self.error(500)
            resp = {
                "status": "error",
                "message": s,
                "data": {
                    "period": self.period,
                    "event_type": self.t
                }
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1
        s =  "Version: %s\n" % __version__
        s += "Period counts for %s events updated" % self.t
        logging.info(s)
        return 0
