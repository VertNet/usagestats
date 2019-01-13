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
__version__ = "ProcessEvents.py 2018-12-11T11:36-03:00"

import json
import logging
from datetime import datetime
from google.appengine.api import mail, taskqueue
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError
from google.appengine.datastore.datastore_query import Cursor
import webapp2
from models import ReportToProcess
from models import QueryCountry, QueryDate, QueryTerms
from models import Report, Search, Download, StatsRun
from config import *

PAGE_SIZE = 10

class ProcessEvents(webapp2.RequestHandler):
    """Process a single resource and create a Report entity."""
    def post(self):

        s =  "Version: %s\n" % __version__
        s += "Arguments from POST:"
        for arg in self.request.arguments():
            s += '\n%s:%s' % (arg, self.request.get(arg))
        logging.info(s)

        # Try to get period from the request in case GetEvents was called directly
        try:
            self.period = self.request.get("period").lower()
            s =  "Version: %s\n" % __version__
            s += "Period %s determined from request: %s" % (self.period, self.request)
            logging.info(s)
        except Exception:
            pass

        # If real period not in request, try to get parameters from StatsRun entity 
        # in case GetEvents was called from a previous task.
        if self.period is None or len(self.period)==0:
            run_key = ndb.Key("StatsRun", 5759180434571264)
            run_entity = run_key.get()
            self.period = run_entity.period

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

        self.github_store = period_entity.github_store
        self.github_issue = period_entity.github_issue

        # Start the loop, until deadline
        try:

            # Prepare query for all Reports to process
            query = ReportToProcess.query()
            query = query.order(ReportToProcess.gbifdatasetid)
            s =  "Version: %s\n" % __version__
            s += "ReportToProcess queried"
            logging.info(s)

            # Get cursor from request, if any
            cursor_str = self.request.get('cursor', None)
            cursor = None
            if cursor_str:
                cursor = Cursor(urlsafe=cursor_str)
            s =  "Version: %s\n" % __version__
            s += "Cursor built: %s" % cursor
            logging.info(s)

            # Initialize loop
            more = True

            # Repeat while there are reports to process
            while more is True:

                # Get the next (or first) round of elements
                logging.info("Fetching %d entities" % PAGE_SIZE)
                results, new_cursor, more = query.fetch_page(
                    PAGE_SIZE, start_cursor=cursor
                )
                s =  "Version: %s\n" % __version__
                s += "Got %d results" % len(results)
                logging.info(s)

                # Process and store transactionally
                self.process_and_store(results)

                # Restart with new cursor (if any)
                if more is True:
                    cursor = new_cursor
                    s =  "Version: %s\n" % __version__
                    s += "New cursor: %s" % cursor.urlsafe()
                    logging.info(s)

            s =  "Version: %s\n" % __version__
            s += "Finished processing reports"
            logging.info(s)

            period_entity = ndb.Key("Period", self.period).get()

            resp = {
                "status": "success",
                "message": "Successfully finished processing all reports",
                "data": {
                    "processed_searches": period_entity.processed_searches,
                    "processed_downloads": period_entity.processed_downloads
                }
            }

            # Launch process to store reports on GitHub, if applicable
            if self.github_store is True:
                resp['message'] += ". Launching GitHub storing process"
                taskqueue.add(url=URI_GITHUB_STORE,
                              queue_name=QUEUENAME)

            # Launch process to create issues on GitHub, if applicable
            elif self.github_issue is True:
                resp['message'] += ". Launching GitHub issue process"
                taskqueue.add(url=URI_GITHUB_ISSUE,
                              queue_name=QUEUENAME)

            # Otherwise, consider finished
            else:
                resp['message'] += ". No GitHub process launched"
                period_entity.status = "done"
                mail.send_mail(
                    sender=EMAIL_SENDER,
                    to=EMAIL_RECIPIENT,
                    subject="Usage reports for period %s" % self.period,
                    body="""
Hey there!

Just a brief note to let you know the extraction of %s stats has 
successfully finished, with no GitHub processes launched.

Congrats!
""" % self.period)

            # In any case, store the status, show message and finish
            period_entity.put()
            logging.info(resp)
            self.response.write(json.dumps(resp)+"\n")

            return

        # When timeout arrives...
        except DeadlineExceededError:
            # Launch new instance with current (failed) cursor
            taskqueue.add(url=URI_PROCESS_EVENTS,
                          params={"cursor": cursor.urlsafe()},
                          queue_name=QUEUENAME)
            s =  "Version: %s\n" % __version__
            s += "Caught a DeadlineExceededError. Relaunching"
            logging.warning(s)

            resp = {
                "status": "in progress",
                "message": "Caught a DeadlineExceededError."
                           " Relaunching with new cursor",
                "data": {
                    "period": self.period,
                    "cursor": cursor.urlsafe()
                }
            }
            logging.info(resp)
            self.response.write(json.dumps(resp)+"\n")

        return

    @ndb.transactional(xg=True)
    def process_and_store(self, results):
        """Process the batch of results into new reports.

This function is executed transactionally, meaning either all reports are
processed and stored or none are. This ensures integrity in the number of
reports that are stored even when the DeadlineExceededError is raised.
"""

        # Batch-process the reports
        reports_to_store, keys_to_delete, counts = self.process_events(results)

        # Batch-store the new Reports
        ndb.put_multi(reports_to_store)

        # Update count in period
        period_entity = ndb.Key("Period", self.period).get()
        period_entity.processed_searches=\
          period_entity.processed_searches+counts['processed_searches']
        period_entity.processed_downloads=\
          period_entity.processed_downloads+counts['processed_downloads']

        period_entity.put()

        # Batch-delete the ReportsToProcess entities
        ndb.delete_multi(keys_to_delete)

    def process_events(self, results):
        """Transform the batch of ReportsToProcess entities into Reports."""

        reports_to_store = []
        keys_to_delete = []
        counts = {"processed_searches": 0, "processed_downloads": 0}

        for resource_entry in results:
            reports_to_store.append(self.process_resource(resource_entry))
            keys_to_delete.append(resource_entry.key)
            if resource_entry.t == "search":
                counts['processed_searches'] += 1
            else:
                counts['processed_downloads'] += 1

        return reports_to_store, keys_to_delete, counts

    def process_resource(self, resource_entry):
        """Transform each ReportToProcess into a proper Report."""

        # Load variables from stored entity
        t = resource_entry.t
        gbifdatasetid = resource_entry.gbifdatasetid
        event = resource_entry.resource

        s =  "Version: %s\n" % __version__
        s += "Processing %s" % gbifdatasetid
        logging.info(s)

        # Extract useful information
        number_of_records = event['records']

        query_countries = [QueryCountry(**x)
                           for x in event['query_countries'].values()]
        query_dates = [QueryDate(query_date=datetime.strptime(
                                                          x['query_date'],
                                                          '%Y-%m-%d'),
                                 times=x['times'])
                       for x in event['query_dates'].values()]
        query_terms = [QueryTerms(**x) for x in event['query_terms'].values()]

        # Build report ID
        report_id = "|".join([self.period, gbifdatasetid])

        # Build dataset key
        dataset_key = ndb.Key("Dataset", gbifdatasetid)

        # Build period key
        period_key = ndb.Key("Period", self.period)

        # QC
        sum_query_countries = 0
        for i in event['query_countries'].values():
            sum_query_countries += i['times']

        sum_query_dates = 0
        for i in event['query_dates'].values():
            sum_query_dates += i['times']

        sum_query_terms = 0
        for i in event['query_terms'].values():
            sum_query_terms += i['times']

        if sum_query_countries != sum_query_dates or \
            sum_query_countries != sum_query_terms or \
                sum_query_dates != sum_query_terms:
            logging.warning("WARNING: lengths of query entities keys list"
                            "do not match:")
            logging.warning("Query countries: %d" % sum_query_countries)
            logging.warning("Query dates: %d" % sum_query_dates)
            logging.warning("Query terms: %d" % sum_query_terms)
            number_of_events = max([sum_query_countries,
                                    sum_query_countries,
                                    sum_query_countries])
        else:
            number_of_events = sum_query_countries

        # Get existing or create new Report entity
        s =  "Version: %s\n" % __version__
        s += "Retrieving existing report or creating new one"
        logging.info(s)
        report = Report.get_or_insert(
            report_id,
            parent=period_key,
            created=datetime.today(),
            reported_period=period_key,
            reported_resource=dataset_key,
            searches=Search(
                events=0,
                records=0,
                query_countries=[],
                query_dates=[],
                query_terms=[],
                # status="in progress"
            ),
            downloads=Download(
                events=0,
                records=0,
                query_countries=[],
                query_dates=[],
                query_terms=[],
                # status="in progress"
            ),
            stored=False,
            issue_sent=False
        )

        # Populate event data
        s =  "Version: %s\n" % __version__
        s += "Storing %s data" % t
        logging.info(s)

        if t == 'search':
            report.searches.records = number_of_records
            report.searches.events = number_of_events
            report.searches.query_countries = query_countries
            report.searches.query_dates = query_dates
            report.searches.query_terms = query_terms
        elif t == 'download':
            report.downloads.records = number_of_records
            report.downloads.events = number_of_events
            report.downloads.query_countries = query_countries
            report.downloads.query_dates = query_dates
            report.downloads.query_terms = query_terms

        return report
