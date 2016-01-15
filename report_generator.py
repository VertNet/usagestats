import json
import logging
from datetime import timedelta
from google.appengine.api.modules import modules
from google.appengine.ext import ndb
import jinja2

from models import Period, CartodbEntry, Dataset, Report, CartodbDownloadEntry
from util import *

from google.appengine.api import urlfetch

import webapp2

__author__ = 'jotegui'

_HOSTNAME = modules.get_hostname(module="tools-usagestats")
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class PeriodListHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)

        # Get all reports on GitHub
        reports_call = urlfetch.fetch(
            url='/'.join([ghb_url, "repos", ghb_org, ghb_rep, "git", "trees", tree_sha]),
            headers=ghb_headers,
            method=urlfetch.GET
        )
        reports = json.loads(reports_call.content)['tree']

        periods = sorted(list(set(["/".join(x['path'].split(".")[0].split("_")[-2:]) for x in reports])))

        resp = {"Processed periods": periods}

        self.response.headers['Content-type'] = "application/json"
        self.response.write(json.dumps(resp))


class StatusHandler(webapp2.RequestHandler):
    def get(self):

        # Check if datasets are loaded in datastore

        # Items in datastore
        d = Dataset.query().count()
        # Items in CDB
        q = "select count(*) as c from resource_staging where ipt is true and networks like '%VertNet%';"
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


class PeriodStatusHandler(webapp2.RequestHandler):
    def get(self, period):

        period_key = ndb.Key("Period", period)
        entity = period_key.get()
        if entity:
            status = entity.status
        else:
            status = "not done"
        getdownloadslist = CartodbDownloadEntry.query(ancestor=period_key).count() > 0

        resp = {
            "Requested period": period,
            "Status of report": status,
        }

        if entity.status == "in progress":
            resp['Extraction status'] = [
                {"Downloads to process": entity.downloads_to_process},
                {"Downloads processed": entity.processed_downloads},
                {"Searches to process": entity.searches_to_process},
                {"Searches processed": entity.processed_searches}
            ]
        elif entity.status == 'done':
            resp['Period data'] = [
                {"Download events": entity.downloads_in_period},
                {"Records downloaded": entity.records_downloaded_in_period},
                {"Search events": entity.searches_in_period},
                {"Records searched": entity.records_searched_in_period},
                {"Distinct datasets in all downloads": entity.downloads_to_process},
                {"Distinct datasets in all searches": entity.searches_to_process}
            ]

        self.response.headers["content-type"] = "application/json"
        self.response.write(json.dumps(resp))


class FutureChecker(webapp2.RequestHandler):
    def post(self):
        futures = self.request.get('futures')

        template = JINJA_ENVIRONMENT.get_template('futures.html')
        self.response.headers["content-type"] = "text/plain"
        self.response.write(template.render(
            futures=futures
        ))