import json
import logging
from datetime import datetime

from google.appengine.api import memcache, mail, taskqueue
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError
from google.appengine.datastore.datastore_query import Cursor
import webapp2

from models import ReportToProcess
from models import QueryCountry, QueryDate, QueryTerms
from models import Report, Search, Download

from config import *

__author__ = "jotegui"

PAGE_SIZE = 10


class ProcessEvents(webapp2.RequestHandler):
    """Process a single resource and create a Report entity."""
    def post(self):

        # Retrieve parameters from memcache and request
        memcache_keys = ["period", "github_store", "github_issue"]
        params = memcache.get_multi(memcache_keys,
                                    key_prefix="usagestats_parser_")
        self.period = params['period']
        self.github_store = params['github_store']
        self.github_issue = params['github_issue']

        # Start the loop, until deadline
        try:

            # Prepare query for all Reports to process
            query = ReportToProcess.query()
            query = query.order(ReportToProcess.gbifdatasetid)
            logging.info("ReportToProcess queried")

            # Get cursor from request, if any
            cursor_str = self.request.get('cursor', None)
            cursor = None
            if cursor_str:
                cursor = Cursor(urlsafe=cursor_str)
            logging.info("Cursor built: %s" % cursor)

            # Initialize loop
            more = True

            # Repeat while there are reports to process
            while more is True:

                # Get the next (or first) round of elements
                logging.info("Fetching %d entities" % PAGE_SIZE)
                results, new_cursor, more = query.fetch_page(
                    PAGE_SIZE, start_cursor=cursor
                )
                logging.info("Got %d results" % len(results))

                # Process and store transactionally
                self.process_and_store(results)

                # Restart with new cursor (if any)
                if more is True:
                    cursor = new_cursor
                    logging.info("New cursor: %s" % cursor.urlsafe())

            logging.info("Finished processing reports")

            # Store memcache'd counts
            counts = memcache.get_multi([
                "processed_searches",
                "processed_downloads"
                ], key_prefix="usagestats_parser_")
            period_entity = ndb.Key("Period", self.period).get()
            period_entity.processed_searches = counts['processed_searches']
            period_entity.processed_downloads = counts['processed_downloads']

            resp = {
                "status": "success",
                "message": "Successfully finished processing all reports",
                "data": {
                    "processed_searches": counts['processed_searches'],
                    "processed_downloads": counts['processed_downloads']
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

Just a brief note to let you know the extraction of %s stats has successfully
finished, with no GitHub processes launched.

Congrats!
""" % self.period)

            # In any case, store the counts, show message and finish
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
            logging.info("Caught a DeadlineExceededError. Relaunching")

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
        memcache.offset_multi(counts, key_prefix="usagestats_parser_")

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

        logging.info("Processing %s" % gbifdatasetid)

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
        logging.info("Retrieving existing report or creating new one")
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
        logging.info("Storing %s data" % t)

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
