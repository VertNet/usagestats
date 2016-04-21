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


class PeriodStatus(webapp2.RequestHandler):
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


# class FutureChecker(webapp2.RequestHandler):
#     def post(self):
#         futures = self.request.get('futures')

#         template = JINJA_ENVIRONMENT.get_template('futures.html')
#         self.response.headers["content-type"] = "text/plain"
#         self.response.write(template.render(
#             futures=futures
#         ))

# class PeriodListHandler(webapp2.RequestHandler):
#     def get(self):
#         urlfetch.set_default_fetch_deadline(60)

#         # Get all reports on GitHub
#         reports_call = urlfetch.fetch(
#             url='/'.join([ghb_url, "repos", ghb_org, ghb_rep, "git",
#                           "trees", tree_sha]),
#             headers=ghb_headers,
#             method=urlfetch.GET
#         )
#         reports = json.loads(reports_call.content)['tree']

#         periods = sorted(list(set(["/".join(x['path'].split(".")[0]\
#                                   .split("_")[-2:]) for x in reports])))

#         resp = {"Processed periods": periods}

#         self.response.headers['Content-type'] = "application/json"
#         self.response.write(json.dumps(resp))