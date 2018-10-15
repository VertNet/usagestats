# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = '@jotegui'
__contributors__ = "Javier Otegui, John Wieczorek"
__copyright__ = "Copyright 2018 vertnet.org"
__version__ = "GitHubIssue.py 2018-10-15T00:18-03:00"

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

PAGE_SIZE = 1

class GitHubIssue(webapp2.RequestHandler):
    """Create an issue for each report in its corresponding GitHub repo."""
    def post(self):

        # Get parameters from memcache
        memcache_keys = ["period", "testing"]
        params = memcache.get_multi(memcache_keys, key_prefix="usagestats_parser_")

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
            s =  "Version: %s\n" % __version__
            s += "Response: %s" % resp
            logging.error(s)
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
            s =  "Version: %s\n" % __version__
            s += "Provided period does not exist in datastore: %s" % self.period
            logging.error(s)
            self.response.write(json.dumps(resp)+"\n")
            return

        # Try to get 'testing' from memcache
        try:
            self.testing = params['testing']
        # If not in memcache (i.e., if called directly), get from request
        except KeyError:
            self.testing = self.request.get('testing').lower() == 'true'

        # Prepare list of reports to store
        s =  "Version: %s\n" % __version__
        s += "Getting list of reports to send issue"
        logging.info(s)

        # Base query
        reports_q = Report.query()

        # Only Reports for current Period
        reports_q = reports_q.filter(Report.reported_period == period_key)

        # Only those with 'issue_sent' property set to False
        reports_q = reports_q.filter(Report.issue_sent == False)

        # Only those with 'report_stored' property set to True
        reports_q = reports_q.filter(Report.stored == True)

        # Store final query
        reports_query = reports_q

        s =  "Version: %s\n" % __version__
        s += "Found %d Reports to send issues for." % reports_query.count()
        logging.info(s)

        # Get cursor from request, if any
        cursor_str = self.request.get("cursor", None)
        cursor = None
        if cursor_str:
            cursor = ndb.Cursor(urlsafe=cursor_str)
            s =  "Version: %s\n" % __version__
            s += "Cursor built: %s" % cursor
            logging.info(s)

        # Initialize loop
        if reports_query.count==0:
            more = False
        else:
            more = True

        # Loop until DeadlineExceededError
        try:
            datasets=[]
            # or until no more reports left
            while more is True:

                s =  "Version: %s\n" % __version__
                s += "Issuing query: %s" % reports_query
                logging.info(s)

                # Get next (or first) round of results
                report, new_cursor, more = reports_query.fetch_page(
                    PAGE_SIZE, start_cursor=cursor
                )

                # Check to see if there is actually another report
                if report is not None and len(report) != 0:
                    # Send issue
                    self.send_issue(report[0])
                    gbifdatasetid = report[0].reported_resource.id()
                    datasets.append(gbifdatasetid)

                if more is True:
                    cursor = new_cursor

            s =  "Version: %s\n" % __version__
            s += "Finished creating all issues"
            logging.info(s)

            resp = {
                "status": "success",
                "message": s,
            }

            period_entity.status = "done"
            mail.send_mail(
                sender=EMAIL_SENDER,
                to=EMAIL_ADMINS,
                subject="Usage reports for period %s" % self.period,
                body="""
Hey there!

Just a note to let you know the GitHubIssue process for period %s 
stats has successfully finished. Reports have been stored in their 
respective GitHub repositories and issues have been created. 

Issues submitted for datasets:
%s

Code version: %s
""" % (self.period, datasets, __version__) )

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
            s =  "Version: %s\n" % __version__
            s += "Caught a DeadlineExceededError. Relaunching."
            logging.info(s)

            resp = {
                "status": "in progress",
                "message": s,
                "data": {
                    "period": self.period,
                    "cursor": cursor.urlsafe()
                }
            }
            s =  "Version: %s\n" % __version__
            s += "Response: %s" % resp
            logging.info(s)
            self.response.write(json.dumps(resp)+"\n")

        return

    def send_issue(self, report_entity):
        """."""

        report_key = report_entity.key
        s =  "Version: %s\n" % __version__
        s += "Ready to send issue %s" % report_key.id()
        logging.info(s)

        gbifdatasetid = report_entity.reported_resource.id()
        s =  "Version: %s\n" % __version__
        s += "Storing issue for dataset %s" % gbifdatasetid
        logging.info(s)

        # Build variables
        dataset_key = report_entity.reported_resource
        period_key = report_entity.reported_period
        dataset_entity, period_entity = ndb.get_multi([dataset_key, period_key])

        # Check that dataset exists
        if not dataset_entity:
            self.error(500)
            resp = {
                "status": "error",
                "message": "Missing dataset in datastore."
                           " Please run /setup_datasets to fix",
                "data": {
                    "missing_dataset_key": gbifdatasetid
                }
            }
            s =  "Version: %s\n" % __version__
            s += "Response: %s" % resp
            logging.error(s)
            self.response.write(json.dumps(resp)+"\n")

            # Set 'issue_sent' to True to avoid endless loop in the case a dataset does
            # not exist in the datastore.
            # TODO: Better if the Report entity had a flag for 'issue_skipped'
            # with default None. But, for now...
            report_entity.issue_sent = True

            # Store updated version of Report entity
            report_entity.put()

            return

        # GitHub stuff
        org = dataset_entity.github_orgname
        repo = dataset_entity.github_reponame
        user_agent = 'VertNet'
        key = apikey('ghb')

        # Testing block
        if self.testing:
            org = 'VertNet'
            repo = 'statReports'
            user_agent = 'VertNet'
            key = apikey('ghb')
#             logging.info("Using testing repositories in jotegui")
#             org = 'jotegui'
#             repo = 'statReports'
#             user_agent = 'jotegui'
#             key = apikey('jot')

        s =  "Version: %s\n" % __version__
        s += "Using GitHub repository %s/%s " % (org, repo)
        s += "as user_agent %s" % user_agent
        logging.info(s)

        # GitHub request headers
        headers = {
            'User-Agent': user_agent,
            'Authorization': 'token {0}'.format(key),
            "Accept": "application/vnd.github.v3+json"
        }

        # Issue creation, only if issue not previously created
        if report_entity.issue_sent is False:

#            link = "http://" + MODULE + "/reports/" + gbifdatasetid + \
#                    "/" + self.period + "/"
#            link_all = "http://" + MODULE + "/reports/" + gbifdatasetid + "/"
            link_all = "http://%s/reports/%s/" % (MODULE, gbifdatasetid)
            link = "http://%s/reports/%s/%s/" % (MODULE, gbifdatasetid, self.period)
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
            # HTTP 201 = Success
            if r.status_code == 201:
                s =  "Version: %s\n" % __version__
                s += "Status: %s. Issue %s sent." % (r.status_code, report_key.id())
                logging.info(s)
                report_entity.issue_sent = True
            # Other generic problems
            else:
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
                s =  "Version: %s\n" % __version__
                s += "Response: %s. " % resp
                logging.error(s)
                return

        # This 'else' should NEVER happen
        else:
            s =  "Version: %s\n" % __version__
            s += "Issue for %s was already sent, " % report_key.id()
            s += "but 'issue_sent' property was 'False'. "
            s += "This call should not have happened."
            logging.error(s)

        # Store updated version of Report entity
        report_entity.put()

        # Wait 2 seconds to avoid GitHub abuse triggers
        time.sleep(2)

        return
