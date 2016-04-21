import time
import json
import logging

from google.appengine.api import memcache, taskqueue, mail, urlfetch
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError
import webapp2

from models import Report

from config import *
from util import apikey

__author__ = "jotegui"

PAGE_SIZE = 1


class GitHubIssue(webapp2.RequestHandler):
    """Create an issue for each report in its corresponding GitHub repo."""
    def post(self):

        # Get parameters from memcache
        memcache_keys = ["period", "testing"]
        params = memcache.get_multi(memcache_keys,
                                    key_prefix="usagestats_parser_")

        # Try to get 'params' from memcache
        try:
            self.period = params['period']
        # If not in memcache (i.e., if called directly), get from request
        except KeyError:
            self.period = self.request.get("period")

        # If still not there, halt
        if not self.period:
            self.error(400)
            resp = {
                "status": "error",
                "message": "Period parameter was not provided."
            }
            logging.error(resp)
            self.response.write(json.dumps(resp)+"\n")
            return
        else:
            memcache.set("usagestats_parser_period", self.period)

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

        # Try to get 'testing' from memcache
        try:
            self.testing = params['testing']
        # If not in memcache (i.e., if called directly), get from request
        except KeyError:
            self.testing = self.request.get('testing').lower() == 'true'

        # Prepare list of reports to store
        logging.info("Getting list of reports to send issue")

        # Base query
        reports_q = Report.query()

        # Only Reports for current Period
        reports_q = reports_q.filter(Report.reported_period == period_key)

        # Only those with 'issue_sent' property set to False
        reports_q = reports_q.filter(Report.issue_sent == False)

        # Store final query
        reports_query = reports_q

        logging.info("Found %d Reports to send issue" % reports_query.count())

        # Get cursor from request, if any
        cursor_str = self.request.get("cursor", None)
        cursor = None
        if cursor_str:
            cursor = ndb.Cursor(urlsafe=cursor_str)
            logging.info("Cursor built: %s" % cursor)

        # Initialize loop
        more = True

        # Loop until DeadlineExceededError
        try:
            # or until no more reports left
            while more is True:

                # Get next (or first) round of results
                report, new_cursor, more = reports_query.fetch_page(
                    PAGE_SIZE, start_cursor=cursor
                )

                # Send issue
                self.send_issue(report[0])

                if more is True:
                    cursor = new_cursor

            logging.info("Finished creating all issues")

            resp = {
                "status": "success",
                "message": "Successfully finished creating all issues",
            }

            period_entity.status = "done"
            mail.send_mail(
                sender=EMAIL_SENDER,
                to=EMAIL_RECIPIENT,
                subject="Usage reports for period %s" % self.period,
                body="""
Hey there!

Just a brief note to let you know the extraction of %s stats has successfully
finished, all reports have been stored in their respective GitHub
repositories and issues have been created. The full package.

Congrats!
""" % self.period)

            # In any case, store period data, show message and finish
            period_entity.put()
            logging.info(resp)
            self.response.write(json.dumps(resp)+"\n")

            return

        except DeadlineExceededError:
            # Launch new instance with current (failed) cursor
            taskqueue.add(url=URI_GITHUB_ISSUE,
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

    def send_issue(self, report_entity):
        """."""

        report_key = report_entity.key
        logging.info("Ready to send issue to %s" % report_key.id())

        gbifdatasetid = report_entity.reported_resource.id()
        logging.info("Sending issue for dataset {0}".format(gbifdatasetid))

        # Build variables
        dataset_key = report_entity.reported_resource
        period_key = report_entity.reported_period
        dataset_entity, period_entity = ndb.get_multi([dataset_key,
                                                       period_key])

        # Check that dataset exists
        if not dataset_entity:
            self.error(500)
            resp = {
                "status": "error",
                "message": "Missing dataset in datastore."
                           " Please run /setup_datasets to fix",
                "data": {
                    "missing_dataset_key": dataset_key
                }
            }
            logging.error(resp)
            self.response.write(json.dumps(resp)+"\n")
            return

        # GitHub stuff
        org = dataset_entity.github_orgname
        repo = dataset_entity.github_reponame
        logging.info(org)
        logging.info(repo)
        key = apikey('ghb')
        user_agent = 'VertNet'

        # Testing block
        if self.testing:
            logging.info("Using testing repositories in jotegui")
            org = 'jotegui'
            repo = 'statReports'
            user_agent = 'jotegui'
            key = apikey('jot')

        # GitHub request headers
        headers = {
            'User-Agent': user_agent,
            'Authorization': 'token {0}'.format(key),
            "Accept": "application/vnd.github.v3+json"
        }

        # Issue creation, only if issue not previously created
        if report_entity.issue_sent is False:

            link = "http://" + MODULE + "/reports/" + gbifdatasetid + \
                    "/" + self.period + "/"
            link_all = "http://" + MODULE + "/reports/" + gbifdatasetid + "/"

            title = 'Monthly VertNet data use report for %s-%s, resource %s' \
                    % (period_entity.year,
                       period_entity.month,
                       dataset_entity.ccode)
            body = """Your monthly VertNet data use report is ready!
You can see the HTML rendered version of the reports with this link:

{0}

Raw text and JSON-formatted versions of the report are also available for
download from this link. In addition, a copy of the text version has been
uploaded to your GitHub repository, under the "Reports" folder. Also, a full
list of all reports can be accessed here:

{1}

You can find more information on the reporting system, along with an
explanation of each metric, here:

http://www.vertnet.org/resources/usagereportingguide.html

Please post any comments or questions to:
http://www.vertnet.org/feedback/contact.html

Thank you for being a part of VertNet.
""".format(link, link_all)
            labels = ['report']

            request_url = '{0}/{1}/{2}/issues'.format(GH_REPOS, org, repo)
            json_input = json.dumps({
                'title': title,
                'body': body,
                'labels': labels
            })

            # Make GitHub call
            r = urlfetch.fetch(
                url=request_url,
                method=urlfetch.POST,
                headers=headers,
                payload=json_input
            )

            # Check output
            logging.info(r.status_code)

            # HTTP 201 = Success
            if r.status_code == 201:
                logging.info("Issue %s successfully sent" % report_key.id())
                report_entity.issue_sent = True
            # Other generic problems
            else:
                logging.error("Issue %s couldn't be sent" % report_key.id())
                logging.error(r.content)
                resp = {
                    "status": "failed",
                    "message": "Got uncaught error code when uploading"
                               " report to GitHub. Aborting issue creation.",
                    "source": "send_to_github",
                    "data": {
                        "report_key": report_key,
                        "period": self.period,
                        "testing": self.testing,
                        "error_code": r.status_code,
                        "error_content": r.content
                    }
                }
                logging.error(resp)
                return

        # This 'else' should NEVER happen
        else:
            logging.warning("Issue for %s was already sent. This call"
                            " shouldn't have happened" % report_key.id())

        # Store updated version of Report entity
        report_entity.put()

        # Wait 2 seconds to avoid GitHub abuse triggers
        time.sleep(2)

        return
