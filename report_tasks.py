import base64
import json
import logging
from datetime import datetime, timedelta
import time
from jinjafilters import JINJA_ENVIRONMENT

from models import Period, Report, Search, Download, QueryCountry, QueryDate, QueryTerms
from util import add_time_limit, cartodb_query, geonames_query, apikey

from google.appengine.api import modules, urlfetch
from google.appengine.ext import ndb, deferred
import webapp2

__author__ = 'jotegui'

# URLs
MODULE_NAME = "tools-usagestats"
MODULE = modules.get_hostname(module = MODULE_NAME)

GETEVENTSLIST = "/parser/geteventslist/"
GETEVENTSLIST_FULL = "http://" + MODULE + GETEVENTSLIST

PARSEEVENTSLIST = "/parser/parseeventslist/"
PARSEEVENTSLIST_FULL = "http://" + MODULE + PARSEEVENTSLIST

PROCESSEVENTS = "/parser/processevents/"
PROCESSEVENTS_FULL = "http://" + MODULE + PROCESSEVENTS


class ProcessPeriod(webapp2.RequestHandler):
    def post(self):
        self.get(period = self.request.get('period'))

    def get(self, period, github=True, testing=False):
        if len(period) == 6:
            y, m = (int(period[:4]), int(period[-2:]))
            p = Period(id = period)
            p.year = y
            p.month = m
            p.status = 'in progress'
            p.put()

            if github is True:
                if testing is True:
                    logging.info("Launching tasks with TESTING repos")
                else:
                    logging.info("Launching tasks with FINAL repos")
            else:
                logging.info("Launching tasks WITHOUT repos")

            # Launching GetEventsList task for downloads and searches
            for t in ['download', 'search']:

                logging.info("Launching 'GetEventList' task on url %s" % GETEVENTSLIST)
                params = {'period': period, 't': t, 'github': github, 'testing': testing}

                deferred.defer(get_events_list, params=params)

            # # TODO Build response
            # self.response.headers['content-type'] = "application/json"
            # self.response.write(json.dumps({"task": str(task)}))

        else:
            self.error(400)
            self.response.write(json.dumps({"error": "Malformed period"}))


class ProcessPeriodNoGithub(webapp2.RequestHandler):
    def post(self):
        self.get(period=self.request.get('period'))

    def get(self, period):
        pp = ProcessPeriod()
        pp.get(period=period, github=False)


class ProcessPeriodTestingGithub(webapp2.RequestHandler):
    def post(self):
        self.get(period=self.request.get('period'))

    def get(self, period):
        pp = ProcessPeriod()
        pp.get(period=period, testing=True)


def get_events_list(params):

    period = params['period']
    t = params['t']
    github = params['github']
    testing = params['testing']

    logging.info("Building %s query" % t)
    if t == 'download':
        query = "SELECT cartodb_id, lat, lon, created_at, query AS query_terms, response_records, " \
                "results_by_resource FROM query_log_master " \
                "WHERE type='download' AND download IS NOT NULL AND download !=''"
    else:
        query = "SELECT cartodb_id, lat, lon, created_at, query AS query_terms, response_records, " \
                "results_by_resource FROM query_log_master " \
                "WHERE left(type, 5)='query' AND results_by_resource IS NOT NULL " \
                "AND results_by_resource != '{}' AND results_by_resource !=''"

    query += " and client='portal-prod'"  # Just production portal downloads
    queried_date = datetime(int(period[:4]), int(period[-2:]), 1)
    queried_date += timedelta(days = 32)
    query = add_time_limit(query = query, today = queried_date)  # Just from the specific month

    logging.info("Executing query")
    data = cartodb_query(query)
    logging.info("Extracted %d entities" % len(data))

    logging.info("Formatting results")
    resources = {}

    for event in data:

        # Preformat some fields
        event_created = datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        event_created = event_created.strftime('%Y-%m-%d')  # Keep just YMD to avoid ast crying
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

    # Get Period entity
    period_key = ndb.Key("Period", period)
    period_entity = period_key.get()

    # Update (downloads|searches)_in_period and (downloads|searches)_to_process in Period
    if t == 'download':
        period_entity.downloads_in_period = len(data)
        period_entity.records_downloaded_in_period = sum([int(x['response_records']) for x in data])
        period_entity.downloads_to_process = len(resources)
    elif t == 'search':
        period_entity.searches_in_period = len(data)
        period_entity.records_searched_in_period = sum([int(x['response_records']) for x in data])
        period_entity.searches_to_process = len(resources)

    # Store updated period data
    period_entity.put()

    for resource in resources:
        logging.info("Sending %s to deferred function" % resource)
        params = {
            "period": period,
            "type": t,
            "gbifdatasetid": resource,
            "res": resources[resource],
            "github": github,
            "testing": testing
        }

        deferred.defer(process_events, params=params)

    # # TODO Build response
    # resp = {
    #     "resp_keys": resp_keys
    # }
    # self.response.headers['content-type'] = "application/json"
    # self.response.write(json.dumps(resp))


@ndb.transactional()
def process_events(params):

    period = params['period']
    t = params['type']
    gbifdatasetid = params['gbifdatasetid']
    event = params['res']
    github = params['github']
    testing = params['testing']

    logging.info("Processing %s" % gbifdatasetid)

    # Extracting useful information
    number_of_records = event['records']

    query_countries = [QueryCountry(**x) for x in event['query_countries'].values()]
    query_dates = [QueryDate(query_date = datetime.strptime(x['query_date'], '%Y-%m-%d'),
                             times = x['times']) for x in event['query_dates'].values()]
    query_terms = [QueryTerms(**x) for x in event['query_terms'].values()]

    # Build report ID
    report_id = "|".join([period, gbifdatasetid])

    # Build dataset key
    dataset_key = ndb.Key("Dataset", gbifdatasetid)

    # Build period key
    period_key = ndb.Key("Period", period)

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
        logging.warning("WARNING: lengths of query entities keys list do not match:")
        logging.warning("Query countries: %d" % sum_query_countries)
        logging.warning("Query dates: %d" % sum_query_dates)
        logging.warning("Query terms: %d" % sum_query_terms)
        number_of_events = max([sum_query_countries, sum_query_countries, sum_query_countries])
    else:
        number_of_events = sum_query_countries

    # Get existing or create new Report entity
    logging.info("Retrieving existing report or creating new one")
    report = Report.get_or_insert(
        report_id,
        parent = period_key,
        # url = ndb.Key('Period', period, 'Report', report_id).urlsafe(),
        created = datetime.today(),
        reported_period = period_key,
        reported_resource = dataset_key,
        searches = Search(
            events = 0,
            records = 0,
            query_countries = [],
            query_dates = [],
            query_terms = [],
            # status = "in progress"
        ),
        downloads = Download(
            events = 0,
            records = 0,
            query_countries = [],
            query_dates = [],
            query_terms = [],
            # status = "in progress"
        )
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

    # Store for putting
    report_key = report.put()
    logging.info("Finished processing %s data for %s" % (t, gbifdatasetid))

    # Update count in period
    p = period_key.get()
    if t == 'search':
        p.processed_searches += 1
    elif t == 'download':
        p.processed_downloads += 1
    if p.processed_downloads == p.downloads_to_process and p.processed_searches == p.searches_to_process:
        p.status = 'done'
        logging.info("Reports for all datasets generated")
        if github is True:
            # Send GitHub notifications serially
            logging.info("Sending GitHub notifications")
            params = {
                "period": period,
                "testing": testing
            }
            deferred.defer(send_all_to_github, params=params)
        else:
            logging.info("Skipping GitHub notifications")
    else:
        p.status = 'failed'
        logging.warning("Processing period failed. Not all searches/downloads were processed")
    p.put()

    # # TODO: Build response
    # # Building response
    # resp = {
    #     "key": str(report_key)
    # }
    # self.response.headers['content-type'] = 'application/json'
    # self.response.write(json.dumps(resp))


def send_all_to_github(params):

    period = params['period']
    testing = params['testing']

    period_key = ndb.Key("Period", period)

    report_keys = Report.query(Report.reported_period == period_key).fetch(keys_only=True)

    for report_key in report_keys:

        send_to_github(report_key, period, testing)

        time.sleep(2)


def send_to_github(report_key, period, testing):

        gbifdatasetid = report_key.id().split("|")[1]
        logging.info("Sending issue for dataset {0}".format(gbifdatasetid))

        # Build variables
        dataset_key = ndb.Key("Dataset", gbifdatasetid)
        dataset_entity = dataset_key.get()
        period_key = ndb.Key("Period", period)
        period_entity = period_key.get()
        report_entity = report_key.get()

        # GitHub stuff
        org = dataset_entity.github_orgname
        repo = dataset_entity.github_reponame
        logging.info(org)
        logging.info(repo)
        key = apikey('ghb')

        headers = {
            'User-Agent': 'VertNet',
            'Authorization': 'token {0}'.format(key),
            "Accept": "application/vnd.github.v3+json"
        }

        # Testing block
        if testing:
            logging.info("Using testing repositories in jotegui")
            org = 'jotegui'
            repo = 'statReports'

        # Upload txt report to GitHub
        template = JINJA_ENVIRONMENT.get_template('report.txt')
        content = template.render(
            dataset=dataset_entity,
            report=report_entity,
            period=period_entity
        )
        message = content.split("\n")[1]  # 2nd line of txt report
        path = "reports/{0}.txt".format("-".join([dataset_entity.icode, dataset_entity.ccode, "-".join([period[:4], period[4:]])]))
        logging.info(path)
        content_enc = base64.b64encode(content.encode('utf-8'))
        commiter = {'name': 'VertNet', 'email': 'vertnetinfo@vertnet.org'}  # I think API token overrides this
        json_input = json.dumps({"message": message, "commiter": commiter, "content": content_enc})
        request_url = 'https://api.github.com/repos/{0}/{1}/contents/{2}'.format(org, repo, path)
        logging.info(request_url)
        r = urlfetch.fetch(
            url=request_url,
            method=urlfetch.PUT,
            headers=headers,
            payload=json_input
        )
        logging.info(r.status_code)
        if r.status_code == 201:
            logging.info("Report successfully stored.")
            report_entity.stored = True
        else:
            logging.error("Report could not be stored.")
            logging.error(r.content)
            report_entity.stored = False

        # Issue creation
        link = "http://"+MODULE+"/reports/"+gbifdatasetid+"/"+period+"/"
        link_all = "http://"+MODULE+"/reports/"+gbifdatasetid+"/"

        title = 'Monthly VertNet data use report for {0}-{1}, resource {2}'.format(period_entity.year, period_entity.month, dataset_entity.ccode)
        body = """Your monthly VertNet data use report is ready!
You can see the HTML rendered version of the reports with this link:

{0}

Raw text and JSON-formatted versions of the report are also available for download from this link.
Also, a full list of all reports can be accessed here:

{1}

You can find more information on the reporting system, along with an explanation of each metric, here: http://www.vertnet.org/resources/usagereportingguide.html
Please post any comments or questions to http://www.vertnet.org/feedback/contact.html
Thank you for being a part of VertNet.
""".format(link, link_all)
        labels = ['report']

        url = 'https://api.github.com/repos/{0}/{1}/issues'.format(org, repo)
        data = json.dumps({'title': title, 'body': body, 'labels': labels})

        r = urlfetch.fetch(
            url=url,
            method=urlfetch.POST,
            headers=headers,
            payload=data
        )
        logging.info(r.status_code)
        if r.status_code == 201:
            logging.info("Issue successfully sent.")
            report_entity.issue_sent = True
        else:
            logging.error("Issue could not be sent:")
            logging.error(r.content)
            report_entity.issue_sent = False

        # Store "stored" and "issue_sent" properties
        report_entity.put()

        return
