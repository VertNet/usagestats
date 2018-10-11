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
__version__ = "GitHubStore.py 2018-10-11T18:10-03:00"
GitHubStore_VERSION=__version__

import time
import base64
import json
import logging
from google.appengine.api import memcache, taskqueue, urlfetch, mail
from google.appengine.ext import ndb
from google.appengine.runtime import DeadlineExceededError
import webapp2
from models import Report
from config import *
from jinjafilters import JINJA_ENVIRONMENT
from util import apikey

PAGE_SIZE = 1

class GitHubStore(webapp2.RequestHandler):
    """Store each report in its corresponding GitHub repository."""
    def post(self):

        # Get parameters from memcache
        memcache_keys = ["period", "testing", "github_issue"]
        params = memcache.get_multi(memcache_keys,
                                    key_prefix="usagestats_parser_")

        # Try to get 'params' from memcache
        try:
            self.period = params['period']
        # If not in memcache (i.e., if called directly), get from request
        except KeyError:
            self.period = self.request.get("period", None)

        # If still not there, halt
        if not self.period:
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

        # Try to get 'github_issue' from memcache
        try:
            self.github_issue = params['github_issue']
        # If not in memcache (i.e., if called directly), get from request
        except KeyError:
            self.github_issue = self.request.get('github_issue')\
                                .lower() == 'true'

        # Prepare list of reports to store
        s =  "Version: %s\n" % __version__
        s += "Getting list of reports to store"
        logging.info(s)

        # Base query
        reports_q = Report.query()

        # Only Reports for current Period
        reports_q = reports_q.filter(Report.reported_period == period_key)

        # Only those with 'stored' property set to False
        reports_q = reports_q.filter(Report.stored == False)

        # Store final query
        reports_query = reports_q

        s =  "Version: %s\n" % __version__
        s += "Found %d Reports to store" % reports_query.count()
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
            # or until no more reports left to store
            while more is True:

                # Get next (or first) round of results
                report, new_cursor, more = reports_query.fetch_page(
                    PAGE_SIZE, start_cursor=cursor
                )

                # Check to see if there is actually another report
                if report is not None and len(report) != 0:
                    # Store extracted report
                    self.store_report(report[0])
                    more = False

                if more is True:
                    cursor = new_cursor

            s =  "Version: %s\n" % __version__
            s += "Finished storing all reports"
            logging.info(s)

            resp = {
                "status": "success",
                "message": s,
            }

            # Launch process to create issues on GitHub, if applicable
            if self.github_issue is True:
                resp['message'] += ". Launching GitHub issue process"
                taskqueue.add(url=URI_GITHUB_ISSUE,
                              queue_name=QUEUENAME)

            # Otherwise, consider finished
            else:
                resp['message'] += ". No GitHub process launched"
                period_entity.status = "done"
                mail.send_mail(
                    sender=EMAIL_SENDER,
                    to=EMAIL_RECIPIENT,
                    subject="Usage reports for period %s" % self.period,
                    body="""
Hey there!

Just a brief note to let you know the extraction of %s stats has successfully
finished, and all reports have been stored in their respective GitHub
repositories (but no issue was created).

Code version: %s

Congrats!
""" % (__version__,self.period) )

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
            s += "Caught a DeadlineExceededError. Relaunching"
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
        """."""

        report_key = report_entity.key
        s =  "Version: %s\n" % __version__
        s += "Ready to store %s" % report_key.id()
        logging.info(s)

        gbifdatasetid = report_entity.reported_resource.id()
        s =  "Version: %s\n" % __version__
        s += "Storing report for dataset %s" % gbifdatasetid
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
            logging.info(s)
            self.response.write(json.dumps(resp)+"\n")
            # Set 'stored' to True to avoid endless loop in the case a dataset does
            # not exist in the datastore.
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

        # Upload txt report to GitHub, only if not previously stored
        if report_entity.stored is False:

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
            logging.info(path)

            # Build GitHub request URL
            request_url = '{0}/{1}/{2}/contents/{3}'.format(GH_REPOS,
                                                            org, repo, path)
            logging.info(request_url)

            # Make GitHub call
            r = urlfetch.fetch(
                url=request_url,
                method=urlfetch.PUT,
                headers=headers,
                payload=json_input
            )

            # Check output
            logging.info(r.status_code)

            # HTTP 201 = Success
            if r.status_code == 201:
                s =  "Version: %s\n" % __version__
                s += "Report %s successfully stored" % report_key.id()
                logging.info(s)
                report_entity.stored = True
            # HTTP 422 = 'SHA' missing, meaning report was already there
            elif r.status_code == 422:
                s =  "Version: %s\n" % __version__
                s += "Report %s was already stored, but " % report_key.id()
                s += "'stored' property was 'False'. "
                s += "This call should not have happened."
                logging.warning(s)
                s =  "Version: %s\n" % __version__
                s += "Content: " % r.content
                logging.error(s)
                report_entity.stored = True
            # Other generic problems
            else:
                s =  "Version: %s\n" % __version__
                s += "Report %s couldn't be stored" % report_key.id()
                logging.error(s)
                s =  "Version: %s\n" % __version__
                s += "Content: " % r.content
                logging.error(s)
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
                s += "Response: " % resp
                logging.error(s)
                return

        # This 'else' should NEVER happen
        else:
            s =  "Version: %s\n" % __version__
            s += "Report %s was already stored, but " % report_key.id()
            s += "'stored' property was 'False'. "
            s += "This call should not have happened."
            logging.warning(s)

        # Store updated version of Report entity
        report_entity.put()

        # Wait 2 seconds to avoid GitHub abuse triggers
        time.sleep(2)

        return
