import json
import base64
import logging
from datetime import datetime

from util import *
from models import *

from google.appengine.api import urlfetch

import jinja2
from jinjafilters import *

import webapp2

__author__ = 'jotegui'

""" TODO LIST:
- Update template fields to fit new model schema (e.g. search_events)

"""

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

JINJA_ENVIRONMENT.filters['querycountriesformat'] = query_countries_format
JINJA_ENVIRONMENT.filters['querydatesformat'] = query_dates_format
JINJA_ENVIRONMENT.filters['querytermsformat'] = query_terms_format
JINJA_ENVIRONMENT.filters['percentageformat'] = percentage_format


class ReportListHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)

        # Get all reports on GitHub
        reports_call = urlfetch.fetch(
            url='/'.join([ghb_url, "repos", ghb_org, ghb_rep, "git", "trees", tree_sha]),
            headers=ghb_headers,
            method=urlfetch.GET
        )
        reports = json.loads(reports_call.content)['tree']

        # Get all Report entities with SHA
        processed_reports = Report.query(Report.sha != "")
        processed_shas = {}
        for x in processed_reports:
            processed_shas[x.sha] = x.key.urlsafe()

        periods = {}
        resources = {}

        for i in reports:

            # Extract useful variables
            s = i['path'].split(".")[0]
            period = "/".join([s.split("_")[-2], s.split("_")[-1]])
            icode = s.split("-")[0]
            ccode = "_".join(s.split("_")[:-2]).split("-")[1]
            resource = "-".join([icode, ccode])
            sha = i['sha']

            # Try to fetch via sha
            if sha in processed_shas.keys():
                link = "key/%s" % processed_shas[sha]
            else:
                link = "sha/%s" % sha

            try:
                periods[period].append({'resource': resource, 'link': link})
            except KeyError:
                periods[period] = [{'resource': resource, 'link': link}]

            try:
                resources[resource].append({'period': period, 'link': link})
            except KeyError:
                resources[resource] = [{'period': period, 'link': link}]

        reports_available = len(reports)

        template = JINJA_ENVIRONMENT.get_template('reportlist.html')
        self.response.write(template.render(
            reports_available=reports_available,
            periods=periods,
            period_keys=sorted(periods.keys()),
            resources=resources,
            resource_keys=sorted(resources.keys())
        ))


class DatasetHandler(webapp2.RequestHandler):
    def get(self, gbifdatasetid):

        dataset_key = ndb.Key("Dataset", gbifdatasetid)
        dataset = dataset_key.get()

        period_query = Report.query(Report.reported_resource == dataset_key).fetch(keys_only=True)
        period_list = [
            {
                "text":x.id().split("|")[0][:4]+"-"+x.id().split("|")[0][4:],
                "url": x.id().split("|")[0]
            } for x in period_query]

        template = JINJA_ENVIRONMENT.get_template('dataset.html')
        self.response.write(template.render(
            dataset=dataset,
            period_list=period_list,
            periods=len(period_list)
        ))


class ReportHandler(webapp2.RequestHandler):
    def get(self, gbifdatasetid, period):

        report_key = ndb.Key("Period", period, "Report", "|".join([period, gbifdatasetid]))
        report = report_key.get()

        if report is None:
            self.error(404)
            self.response.write("Sorry, that report does not exist (yet)")
            return

        dataset = report.reported_resource.get()
        period = report.reported_period.get()
        template = JINJA_ENVIRONMENT.get_template('report.html')
        self.response.write(template.render(
            dataset=dataset,
            report=report,
            period=period
        ))


class TXTReportHandler(webapp2.RequestHandler):
    def get(self, gbifdatasetid, period):
        urlfetch.set_default_fetch_deadline(60)

        report_key = ndb.Key("Period", period, "Report", "|".join([period, gbifdatasetid]))
        report = report_key.get()
        dataset = report.reported_resource.get()
        period = report.reported_period.get()

        # report_call = urlfetch.fetch(
        #     url='/'.join([ghb_url, "repos", ghb_org, ghb_rep, "git", "blobs", sha]),
        #     headers=ghb_headers,
        #     method=urlfetch.GET
        # )
        # report_enc = json.loads(report_call.content)['content']
        # content = base64.b64decode(report_enc)

        template = JINJA_ENVIRONMENT.get_template('report.txt')
        self.response.headers["content-type"] = "text/plain"
        self.response.write(template.render(
            dataset=dataset,
            report=report,
            period=period
        ))


class JSONReportHandler(webapp2.RequestHandler):
    def get(self, gbifdatasetid, period):
        urlfetch.set_default_fetch_deadline(60)

        report_key = ndb.Key("Period", period, "Report", "|".join([period, gbifdatasetid]))
        report = report_key.get()
        sha = report.sha

        if sha != '':
            report_call = urlfetch.fetch(
                url='/'.join([ghb_url, "repos", ghb_org, ghb_rep, "git", "blobs", sha]),
                headers=ghb_headers,
                method=urlfetch.GET
            )
            report_enc = json.loads(report_call.content)['content']
            content = base64.b64decode(report_enc)
        else:
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
                    content[x]["query_dates"][i]["query_date"] = content[x]["query_dates"][i]["query_date"].strftime("%Y-%m-%d")

            # Transform to JSON
            content = json.dumps(content)
        self.response.headers["content-type"] = "application/json"
        self.response.write(content)


class StoreReportHandler(webapp2.RequestHandler):
    def get(self, sha):

        q = Report.query(Report.sha == sha)
        if q.count() > 0:
            logging.info("Report already processed. Redirecting.")
            k = q.get().key.urlsafe()
            self.redirect("/reports/key/%s/" % k)
            return

        logging.info("Processing SHA %s" % sha)
        urlfetch.set_default_fetch_deadline(60)

        report_call = urlfetch.fetch(
            url='/'.join([ghb_url, "repos", ghb_org, ghb_rep, "git", "blobs", sha]),
            headers=ghb_headers,
            method=urlfetch.GET
        )
        report_enc = json.loads(report_call.content)['content']
        content = json.loads(base64.b64decode(report_enc))

        dataset = Dataset.query(Dataset.url == content['url'])

        if dataset.count() == 0:
            logging.warning("Dataset not found for report url %s" % content['url'])
            self.error(404)
            return

        dataset = dataset.get()

        reported_month = datetime.strptime(content['report_month'], '%Y/%m')

        key_id = "|".join([reported_month.strftime('%Y-%m'), dataset.gbifdatasetid])
        report = Report(id=key_id)
        report.sha = sha
        report.reported_month = reported_month
        report.created = datetime.strptime(content['created_at'], '%Y/%m/%d')
        report.reported_resource = dataset.key

        # Searches
        if 'searches' in content:
            searches = Searches()
            searches.search_events = content['searches']['searches']
            searches.records_searched = content['searches']['records']
            for d in content['searches']['dates']:
                querydate = QueryDate()
                querydate.query_date = datetime.strptime(d['date'], '%Y-%m-%d')
                querydate.times = d['times']
                searches.query_dates.append(querydate)
            for d in content['searches']['countries']:
                querycountry = QueryCountry()
                querycountry.query_country = d['country']
                querycountry.times = d['times']
                searches.query_countries.append(querycountry)
            for d in content['searches']['queries']:
                queryterms = QueryTerms()
                queryterms.query_terms = d['query']
                queryterms.times = d['times']
                queryterms.records = d['records']
                searches.query_terms.append(queryterms)
            report.searches = searches

        # Downloads
        if 'downloads' in content:
            downloads = Downloads()
            downloads.download_events = content['downloads']['downloads']
            downloads.downloads_in_period = content['downloads']['downloads_period']
            downloads.records_downloaded = content['downloads']['records']
            downloads.unique_records = content['downloads']['records_unique']
            for d in content['downloads']['dates']:
                querydate = QueryDate()
                querydate.query_date = datetime.strptime(d['date'], '%Y-%m-%d')
                querydate.times = d['times']
                downloads.query_dates.append(querydate)
            for d in content['downloads']['countries']:
                querycountry = QueryCountry()
                querycountry.query_country = d['country']
                querycountry.times = d['times']
                downloads.query_countries.append(querycountry)
            for d in content['downloads']['queries']:
                queryterms = QueryTerms()
                queryterms.query_terms = d['query']
                queryterms.times = d['times']
                queryterms.records = d['records']
                downloads.query_terms.append(queryterms)
            report.downloads = downloads

        report.put()

        logging.info("Processing finished. Redirecting.")
        self.redirect("/reports/key/%s/" % ndb.Key("Report", key_id).urlsafe())
