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
__version__ = "GitHubStore.py 2018-12-11T13:58-03:00"

import time
import base64
import json
import logging
from google.appengine.api import taskqueue, urlfetch, mail
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError
import webapp2
from models import Report, StatsRun
from config import *
from jinjafilters import JINJA_ENVIRONMENT
from util import apikey

PAGE_SIZE = 1

class GitHubStore(webapp2.RequestHandler):
    """Store each report in its corresponding GitHub repository."""
    def post(self):
        # Create instance variable to track if parameters came from a direct request
        # Or if they came through Period entity
        self.params_from_request = None
        params = None

        s =  "Version: %s\n" % __version__
        s += "Arguments from POST:"
        for arg in self.request.arguments():
            s += '\n%s:%s' % (arg, self.request.get(arg))
        logging.info(s)

        # Try to get period from the request in case GitHubStore was called directly
        self.period = self.request.get("period", None)

        # If real period not in request, try to get parameters from StatsRun entity 
        # in case GetEvents was called from a previous task.
        if self.period is None or len(self.period)==0:
            run_key = ndb.Key("StatsRun", 5759180434571264)
            run_entity = run_key.get()
            self.period = run_entity.period
            self.params_from_request = False
            s =  "Version: %s\n" % __version__
            s += "Period %s determined from StatsRun entity: %s" % (self.period, params)
            logging.info(s)
        else:
            self.params_from_request = True
            s =  "Version: %s\n" % __version__
            s += "Period %s determined from request: %s" % (self.period, self.request)
            logging.info(s)

        if self.period is None or len(self.period)==0:
            self.error(400)
            resp = {
                "status": "error",
                "message": "Period parameter was not provided."
            }
            s =  "Version: %s\n" % __version__
            s += "%s" % resp
            logging.error(s)
            self.response.write(json.dumps(resp)+"\n")
            return

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

        # Get the remaining parameters based on the parameter source
        if self.params_from_request == True: 
            # Get parameters from request

            # 'testing' parameter
            try:
                self.testing = self.request.get('testing').lower() == 'true'
            except Exception:
                # default value for 'testing' if not provided is False
                self.testing = False

            # 'github_issue' parameter
            try:
                self.github_issue = self.request.get('github_issue').lower() == 'true'
            except Exception:
                # default value for 'github_issue' if not provided is False
                self.github_issue = False

            # 'gbifdatasetid' parameter
            try:
                self.gbifdatasetid = self.request.get('gbifdatasetid').lower()
            except Exception:
                # default value for 'gbifdatasetid' if not provided is None
                self.gbifdatasetid = None

            # Store the gbifdatsetid in StatsRun entity for use by GitHubIssues task
            run_key = ndb.Key("StatsRun", 5759180434571264)
            run_entity = run_key.get()
            run_entity.gbifdatasetid=self.gbifdatasetid
            run_entity.put()
        else:
            # Get parameters from Period entity

            # 'testing' parameter
            try:
                self.testing = period_entity.testing
            except Exception:
                self.testing = False

            # 'github_issue' parameter
            try:
                self.github_issue = period_entity.github_issue
            except Exception:
                # default value for 'github_issue' if not provided is False
                self.github_issue = False

            # 'gbifdatasetid' parameter can't be used when called from another task

        # Prepare list of reports to store
        # Base query
        reports_q = Report.query()

        # Only Reports for current Period
        reports_q = reports_q.filter(Report.reported_period == period_key)

        # Only Reports with 'stored' property set to False
        # Actually, it is fine to attempt to write the report no matter what.
        # If it is already there store_report() will catch that.
#        reports_q = reports_q.filter(Report.stored == False)

        # And if there is a gbifdatasetid, filter on that too
        if self.gbifdatasetid is not None and len(self.gbifdatasetid) > 0:
            dataset_key = ndb.Key("Dataset", self.gbifdatasetid)

            if dataset_key is None:
                s =  "Version: %s\n" % __version__
                s += "gbifdatasetid %s not found in data store." % self.gbifdatasetid
                logging.error(s)
                return
            else:
                reports_q = reports_q.filter(Report.reported_resource == dataset_key)

        # Store final query
        reports_query = reports_q

        s =  "Version: %s\n" % __version__
        s += "Found %d Reports to store " % reports_query.count()
        s += "from query %s" % reports_query
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
        # or until there are no more reports left to store
        try:
            # Keep track of dataset for which Reports have been stored in this run
            datasets = []
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
                    # Store extracted report
                    self.store_report(report[0])
                    gbifdatasetid = report[0].reported_resource.id()
                    datasets.append(gbifdatasetid)

                if more is True:
                    cursor = new_cursor

            s =  "Version: %s\n" % __version__
            s += "Finished storing all %d reports" % len(datasets)
            logging.info(s)

            resp = {
                "status": "success",
                "message": s,
            }

            # Launch process to create issues on GitHub, if applicable
            if self.github_issue is True:
                resp['message'] += ". Launching GitHub issue process"
                taskqueue.add(url=URI_GITHUB_ISSUE, queue_name=QUEUENAME)

            # Otherwise, consider finished
            else:
                resp['message'] += ". No GitHub Issues process launched"
                period_entity.status = "done"
                mail.send_mail(
                    sender=EMAIL_SENDER,
                    to=EMAIL_ADMINS,
                    subject="Usage reports for period %s" % self.period,
                    body="""
Hey there!

Just a note to let you know the GitHubStore process for the period %s 
has  successfully finished. Reports have been stored in their respective 
GitHub repositories.

Reports (%d) stored for datasets:
%s

Code version: %s
""" % (self.period, len(datasets), datasets, __version__ ) )

            # In any case, store period data, show message and finish
            period_entity.put()
            s =  "Version: %s\n" % __version__
            s += "Response: %s" % resp
            logging.info(s)
            self.response.write(json.dumps(resp)+"\n")

            return

        except DeadlineExceededError:
            # Launch new instance with current (failed) cursor
            taskqueue.add(url=URI_GITHUB_STORE,
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
            logging.info(resp)
            self.response.write(json.dumps(resp)+"\n")

        return

    def store_report(self, report_entity):
        """Write report file to GitHub."""

        # Build variables
        dataset_key = report_entity.reported_resource
        period_key = report_entity.reported_period
        dataset_entity, period_entity = ndb.get_multi([dataset_key, period_key])
        report_key = report_entity.key
        gbifdatasetid = report_entity.reported_resource.id()

        # Check that dataset exists
        if not dataset_entity:
            self.error(500)
            resp = {
                "status": "error",
                "message": "Missing dataset in datastore. Please run /setup_datasets "
                           "or remove associated Period entity from data store to fix.",
                "data": {
                    "missing_dataset_key": gbifdatasetid
                }
            }
            s =  "Version: %s\n" % __version__
            s += "Response: %s" % resp
            logging.error(s)
            self.response.write(json.dumps(resp)+"\n")

            # Set 'stored' to True to avoid endless loop in the case a dataset does
            # not exist in the datastore.
            # TODO: Better if the Report entity had a flag for 'storage_skipped'
            # with default None. But, for now...
            report_entity.stored = True

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

        # GitHub request headers
        headers = {
            'User-Agent': user_agent,
            'Authorization': 'token {0}'.format(key),
            "Accept": "application/vnd.github.v3+json"
        }

        # Load template
        template = JINJA_ENVIRONMENT.get_template('report.txt')

        # Render template with values from Report
        content = template.render(
            dataset=dataset_entity,
            report=report_entity,
            period=period_entity
        )

        # Build GitHub request parameters: message
        message = content.split("\n")[1]  # 2nd line of txt report

        # Build GitHub request parameters: committer
        committer = GH_COMMITTER

        # Build GitHub request parameters: content
        content_enc = base64.b64encode(content.encode('utf-8'))

        # Build GitHub request parameters
        json_input = json.dumps({
            "message": message,
            "committer": committer,
            "content": content_enc
        })

        # Build GitHub request URL: path
        txt_path = "-".join([dataset_entity.icode,
                            dataset_entity.ccode,
                            "-".join([self.period[:4], self.period[4:]])])
        path = "reports/{0}.txt".format(txt_path)

        s = "Storing at: %s/%s/%s/%s" % (GH_REPOS, org, repo, path)
        logging.info(s)

        # Build GitHub request URL
        request_url = '{0}/{1}/{2}/contents/{3}'.format(GH_REPOS, org, repo, path)

        # Make GitHub call
        r = urlfetch.fetch(
            url=request_url,
            method=urlfetch.PUT,
            headers=headers,
            payload=json_input
        )

        # Check output
        # HTTP 201 = Success
        if r.status_code == 201:
            report_entity.stored = True

            s =  "Report %s sent " % report_key.id()
            s += "for gbifdatasetid %s to %s " % (gbifdatasetid, path)
            logging.info(s)

        # HTTP 422 = 'SHA' missing, meaning report was already there
        elif r.status_code == 422:
            report_entity.stored = True

            s =  "Report %s was already stored " % report_key.id()
            s += "for gbifdatasetid %s at %s " % (gbifdatasetid, path)
            logging.warning(s)

        # Other generic problems
        else:
            resp = {
                "status": "failed",
                "message": "Got uncaught error code when uploading report to GitHub.",
                "source": "send_to_github",
                "data": {
                    "report_key": report_key,
                    "period": self.period,
                    "gbifdatasetid": gbifdatasetid,
                    "github_issue": self.github_issue,
                    "testing": self.testing,
                    "error_code": r.status_code,
                    "error_content": r.content
                }
            }

            s =  "Version: %s\n" % __version__
            s += "Response: " % resp
            logging.error(s)

            return

        # Store updated version of Report entity
        report_entity.put()

        # Wait 2 seconds to avoid GitHub abuse triggers. 1 isn't sufficient.
        time.sleep(2)

        return
