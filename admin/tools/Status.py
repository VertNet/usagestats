import json
# import logging
# from datetime import timedelta
from google.appengine.api.modules import modules
from google.appengine.ext import ndb
import jinja2

from models import Period, Dataset, Report, CartodbDownloadEntry
from util import *

# from google.appengine.api import urlfetch

import webapp2

__author__ = 'jotegui'

_HOSTNAME = modules.get_hostname(module="tools-usagestats")
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                   'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class Status(webapp2.RequestHandler):
    def get(self):

        # Check if datasets are loaded in datastore

        # Items in datastore
        d = Dataset.query().count()
        # Items in CDB
        q = "select count(*) as c from resource_staging" + \
            " where ipt is true and networks like '%VertNet%';"
        c = cartodb_query(q)[0]['c']

        # Number of reports stored in the datastore
        num_reports = Report.query().count()

        periods = Period.query()
        num_periods = periods.count()

        periods_done = Period.query(Period.status == "done")
        num_periods_done = periods_done.count()

        periods_progress = Period.query(Period.status == "in progress")
        num_periods_progress = periods_progress.count()

        periods_failed = Period.query(Period.status == "failed")
        num_periods_failed = periods_failed.count()

        resp = {
            "Datastore integrity": [
                {"Datasets in CartoDB": c},
                {"Datasets in the Datastore": d}
            ],
            "Report periods": [
                {"Stored periods": num_periods},
                {"Stored reports": num_reports},
                {"Periods completed": num_periods_done},
                {"Periods in progress": num_periods_progress},
                {"Periods failed": num_periods_failed},
            ]
        }

        if c != d or c == 0:
            dataset_setup_url = "http://%s/setup_datasets" % _HOSTNAME
            resp["Datastore integrity"].append({"URL for dataset setup": dataset_setup_url})
        if num_periods > 0:
            links_to_periods = ["http://%s/status/period/%s" % (_HOSTNAME, x.key.id()) for x in periods.fetch()]
            resp["Report periods"].append({"Links to periods": links_to_periods})
        if num_periods_done > 0:
            resp['Report periods'].append({'List of periods done': [x.period.strftime("%Y-%m") for x in periods_done.fetch()]})
        if num_periods_progress > 0:
            resp['Report periods'].append({'List of periods in progress': [x.period.strftime("%Y-%m") for x in periods_progress.fetch()]})
        if num_periods_failed > 0:
            resp['Report periods'].append({'List of periods failed': [x.period.strftime("%Y-%m") for x in periods_failed.fetch()]})

        self.response.headers['content-type'] = "application/json"
        self.response.write(json.dumps(resp))
