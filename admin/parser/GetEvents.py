import json
import logging
from datetime import datetime, timedelta

from google.appengine.ext import ndb
from google.appengine.api import memcache, taskqueue
import webapp2

from models import ReportToProcess
from util import ApiQueryMaxRetriesExceededError
from util import add_time_limit, cartodb_query, geonames_query
from config import *

__author__ = "jotegui"


class GetEvents(webapp2.RequestHandler):
    """Download and prepare log events from logging tables."""
    def post(self):

        # Retrieve parameters from memcache and request
        params = memcache.get_multi([
            "period",
            "table_name",
            "searches_extracted",
            "downloads_extracted"
        ], key_prefix="usagestats_parser_")

        # If GetEvents is called directly, no 'period' will be found
        # Then, get Period from request
        try:
            self.period = params['period']
        except KeyError:
            logging.info("Trying to extract 'period' from request")
            self.period = self.request.get("period")

        self.table_name = params['table_name']
        logging.info("Using %s as data table" % self.table_name)
        self.downloads_extracted = params['downloads_extracted']
        self.searches_extracted = params['searches_extracted']

        # Start with downloads
        if self.downloads_extracted is False:
            self.t = "download"
        # and continue with searches
        elif self.searches_extracted is False:
            self.t = "search"
        # if, by mistake, none is True...
        else:
            # ... call 'process_events' and move on
            taskqueue.add(url=URI_PROCESS_EVENTS,
                          queue_name=QUEUENAME)
            return

        # Get events
        err = self.get_events()
        if err:
            return

        # Parse events
        err = self.parse_events()
        if err:
            return

        # Update Period counts
        err = self.update_period_counts()
        if err:
            return

        # Build temporary entities
        logging.info("Storing %d resources" % len(self.resources))
        r = []
        for resource in self.resources:
            params = {
                "t": self.t,
                "gbifdatasetid": resource,
                "resource": self.resources[resource]
            }
            r.append(ReportToProcess(**params))

        # Store temporary entities
        logging.info("Putting %d entities" % len(r))
        sr = ndb.put_multi(r)

        # Check
        if len(sr) != len(r):
            logging.error("Not all resources were put to process.")
            self.error(500)
            resp = {
                "status": "error",
                "message": "Not all resources were put to process.",
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

        # Update memcache
        if self.t == "search":
            memcache.set("usagestats_parser_searches_extracted", True)
        else:
            memcache.set("usagestats_parser_downloads_extracted", True)

        # If both are True, end now
        p = memcache.get_multi(["searches_extracted", "downloads_extracted"],
                               key_prefix="usagestats_parser_")
        if p['searches_extracted'] is True and\
           p['downloads_extracted'] is True:
            # Call 'process_events'
            logging.info("All searches and downloads extracted")
            taskqueue.add(url=URI_PROCESS_EVENTS,
                          queue_name=QUEUENAME)
        else:
            taskqueue.add(url=URI_GET_EVENTS,
                          queue_name=QUEUENAME)

        return

    def get_events(self):
        """Build query and extract records."""

        # Extract CartoDB data, base query
        logging.info("Building %s query" % self.t)
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
        query += " and client='portal-prod'"

        # Only restrict time if using default table
        if self.table_name == CDB_TABLE:
            queried_date = datetime(
                int(self.period[:4]),
                int(self.period[-2:]),
                1
            )
            queried_date += timedelta(days=32)
            query = add_time_limit(query=query, today=queried_date)

        logging.info("Executing query")
        logging.info(query)
        try:
            data = cartodb_query(query)
        except ApiQueryMaxRetriesExceededError:
            self.error(504)
            resp = {
                "status": "error",
                "message": "Could not retrieve data from CartoDB",
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
        logging.info("Extracted %d %s events" % (len(data), self.t))
        return 0

    def parse_events(self):
        """Preformat some special fields and
redistribute records into resources."""

        # Format according to the Model classes
        logging.info("Formatting results")
        resources = {}

        for event in self.data:

            # Preformat some fields
            event_created = datetime.strptime(event['created_at'],
                                              '%Y-%m-%dT%H:%M:%SZ')
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
                    resources[resource]['query_terms'][event_terms]['times'] += 1
                    resources[resource]['query_terms'][event_terms]['records'] += event_results[resource]

        # Store 'resources' in class property
        self.resources = resources

        # Finish method
        logging.info("Created %d resources" % len(self.resources))
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
            logging.error("Could not update %s counts in period" % self.t)
            self.error(500)
            resp = {
                "status": "error",
                "message": "Could not update %s counts in period" % self.t,
                "data": {
                    "period": self.period,
                    "event_type": self.t
                }
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1
        else:
            logging.info("Period counts for %s events updated" % self.t)
        return 0
