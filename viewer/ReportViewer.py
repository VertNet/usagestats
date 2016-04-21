import json

from google.appengine.api import urlfetch
import webapp2

from models import *
from jinjafilters import *

__author__ = 'jotegui'


class ReportViewer(webapp2.RequestHandler):
    def get(self, gbifdatasetid, period):

        report_key = ndb.Key("Period", period,
                             "Report", "|".join([period, gbifdatasetid]))
        report = report_key.get()

        if not report:
            self.error(404)
            self.response.write("Sorry, that report does not exist")
            logging.error("Attempted to view a non-existing report: %s"
                          % gbifdatasetid)
            return

        template = JINJA_ENVIRONMENT.get_template('report.html')
        self.response.write(template.render(
            dataset=report.reported_resource.get(),
            report=report,
            period=report.reported_period.get()
        ))


class TXTReportViewer(webapp2.RequestHandler):
    def get(self, gbifdatasetid, period):
        urlfetch.set_default_fetch_deadline(60)

        report_key = ndb.Key("Period", period,
                             "Report", "|".join([period, gbifdatasetid]))
        report = report_key.get()

        if not report:
            self.error(404)
            self.response.write("Sorry, that report does not exist")
            logging.error("Attempted to view a non-existing report: %s"
                          % gbifdatasetid)
            return

        template = JINJA_ENVIRONMENT.get_template('report.txt')
        self.response.headers["content-type"] = "text/plain"
        self.response.write(template.render(
            dataset=report.reported_resource.get(),
            report=report,
            period=report.reported_period.get()
        ))


class JSONReportViewer(webapp2.RequestHandler):
    def get(self, gbifdatasetid, period):
        urlfetch.set_default_fetch_deadline(60)

        report_key = ndb.Key("Period", period,
                             "Report", "|".join([period, gbifdatasetid]))
        report = report_key.get()
        # sha = report.sha

        # if sha != '':
        #     report_call = urlfetch.fetch(
        #         url='/'.join([ghb_url, "repos",
        #                       ghb_org, ghb_rep,
        #                       "git", "blobs", sha]),
        #         headers=ghb_headers,
        #         method=urlfetch.GET
        #     )
        #     report_enc = json.loads(report_call.content)['content']
        #     content = base64.b64decode(report_enc)
        # else:

        # Get dictionary representation of Report
        content = report.to_dict()

        # Remove unwanted properties
        content.pop("status", None)
        content.pop("sha", None)
        content.pop("url", None)

        # Transform Key properties
        content["reported_period"] = content["reported_period"].id()
        content["reported_resource"] = content["reported_resource"].id()
        content["created"] = content["created"].strftime("%Y-%m-%d")

        # Transform Date properties
        for x in ["downloads", "searches"]:
            for i in range(len(content[x]['query_dates'])):
                content[x]["query_dates"][i]["query_date"] = \
                    content[x]["query_dates"][i]["query_date"].\
                    strftime("%Y-%m-%d")

        # Transform to JSON
        content = json.dumps(content)

        # Return JSON string
        self.response.headers["content-type"] = "application/json"
        self.response.write(content)
