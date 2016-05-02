import json
import logging

from google.appengine.ext import ndb
from google.appengine.api import memcache, taskqueue
import webapp2

from models import Period, ReportToProcess, Report
from config import *

__author__ = "jotegui"


class InitExtraction(webapp2.RequestHandler):
    """Initialize the processing of a Period."""
    def post(self):
        """Parse parameters, call initialization function
and launch searches and downloads extractions."""

        # Parse parameters
        err = self.store_parameters()
        if err:
            return

        # Call initialization function
        err = self.initialize_extraction()
        if err:
            return

        # Create task for extracting events
        taskqueue.add(url=URI_GET_EVENTS,
                      queue_name=QUEUENAME)

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
        self.period = self.request.get('period')
        self.force = self.request.get('force').lower() == 'true'
        self.testing = self.request.get('testing').lower() == 'true'
        self.github_store = self.request.get('github_store').lower() == 'true'
        self.github_issue = self.request.get('github_issue').lower() == 'true'

        # Store in memcache for further reference
        missed = memcache.set_multi({
            # Extraction variables
            "period": self.period,
            "force": self.force,
            "testing": self.testing,
            "github_store": self.github_store,
            "github_issue": self.github_issue,
            # Process tracking variables
            "searches_extracted": False,
            "downloads_extracted": False,
            "processed_searches": 0,
            "processed_downloads": 0
        }, key_prefix="usagestats_parser_")

        if len(missed) > 0:
            logging.warning("Some call parameters were not added " +
                            "to the memcache: {0}".format(missed))
        else:
            logging.info("All call parameters successfully added to memcache")

        return 0

    def initialize_extraction(self, period=None, force=None):
        """Check if Period parameter is valid, if the Period entity already exists
and create a new Period."""
        self.response.headers['Content-Type'] = "application/json"

        # Check that 'period' is provided
        if not self.period:
            logging.error("Period not found on POST body. Aborting.")
            self.error(400)
            resp = {
                "status": "error",
                "message": "Period not found on POST body. " +
                           "Aborting."
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        # Check that 'period' is valid
        if len(self.period) != 6:
            self.error(400)
            resp = {
                "status": "error",
                "message": "Malformed period. Should be YYYYMM (e.g., 201603)"
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        # Get existing period
        period_key = ndb.Key("Period", self.period)
        period_entity = period_key.get()

        # If existing, abort or clear and start from scratch
        if period_entity:
            if self.force is not True:
                logging.error("Period %s already exists. " % self.period +
                              "Aborting. To override, use 'force=true'.")
                resp = {
                    "status": "error",
                    "message": "Period %s already exists. " % self.period +
                               "Aborting. To override, use 'force=true'."
                }
                self.response.write(json.dumps(resp) + "\n")
                return 1
            else:
                logging.warning("Period %s already exists. " % self.period +
                                "Overriding.")
                # Delete Reports referencing period
                r = Report.query().filter(Report.reported_period == period_key)
                to_delete = r.fetch(keys_only=True)
                logging.info("Deleting %d Report entities" % len(to_delete))
                deleted = ndb.delete_multi(to_delete)
                logging.info("%d Report entities removed" % len(deleted))

                # Delete Period itself
                logging.info("Deleting Period %s" % period_key)
                period_key.delete()
                logging.info("Period entity deleted")

        # Create new Period (id=YYYYMM)
        logging.info("Creating new Period %s" % self.period)
        y, m = (int(self.period[:4]), int(self.period[-2:]))
        p = Period(id=self.period)
        p.year = y
        p.month = m
        p.status = 'in progress'
        period_key = p.put()

        # Check
        if period_key:
            logging.info("New Period %s created successfully." % self.period)
            logging.info("New period's key = %s" % period_key)
        else:
            self.error(500)
            logging.error("Could not create new Period %s" % self.period)
            resp = {
                "status": "error",
                "message": "Could not create new Period %s" % self.period
            }
            self.response.write(json.dumps(resp) + "\n")
            return 1

        # Clear temporary entities
        keys_to_delete = ReportToProcess.query().fetch(keys_only=True)
        logging.info("Deleting %d temporal (internal use only) entities"
                     % len(keys_to_delete))
        ndb.delete_multi(keys_to_delete)

        return 0
