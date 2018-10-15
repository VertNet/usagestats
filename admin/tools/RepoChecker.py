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
__version__ = "RepoChecker.py 2018-10-15T11:03-03:00"
REPOCHECKER_VERSION=__version__

import time
import json
import logging

from google.appengine.api import urlfetch, mail
import webapp2

from config import *
from util import apikey, carto_query

class RepoChecker(webapp2.RequestHandler):
    def post(self):
        self.get()

    def get(self):
        self.response.headers['Content-Type'] = 'application/json'

        s = 'REPOCHECKER Version: %s' % REPOCHECKER_VERSION
        s += '\nChecking consistency of repository names between Carto and GitHub.'
        logging.info(s)

        self.failed_repos = []
        self.check_failed_repos()

        res = {
            'result': None
        }

        if len(self.failed_repos) > 0:
            res['failed_repos'] = self.failed_repos
            res['result'] = "error"
            s = 'REPOCHECKER Version: %s' % REPOCHECKER_VERSION
            s += '\nThere were issues in the repository name matching.'
            logging.error(s)

            error_msg = "\n".join([", ".join(x) for x in self.failed_repos])
            mail.send_mail(
                sender=EMAIL_SENDER,
                to=EMAIL_ADMINS,
                subject="Resource name checker failed",
                body="""
Hey there,

This is an automatic message sent by the Resource name checker tool
to inform you that the script found {0} name combinations of github_orgname and
github_reponame in the VertNet Carto resource_staging table that do not correspond to
an organization/repository combination on GitHub. These are the specific
repositories that failed (names as in Carto):

{1}

Please, fix the entries in the resource_staging table and then go to 
{2} to restart the process.

Thank you!
""".format(len(self.failed_repos), error_msg, "http://%s/" % MODULE))

        else:
            res['result'] = "success"
            s = 'REPOCHECKER Version: %s' % REPOCHECKER_VERSION
            s += '\nThe repository consistency check was successful - no errors found.'
            logging.info(s)

        self.response.write(json.dumps(res))
        return

    def check_failed_repos(self):
        """Check repository name consistency between Carto and GitHub."""

        all_repos = self.get_all_repos()
        repos = {}
        headers = {
            'User-Agent': 'VertNet',
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': 'token {0}'.format(apikey('ghb'))
        }

        for repo in all_repos:
            orgname = repo[0]
            reponame = repo[1]

            if orgname is None or reponame is None:
                self.failed_repos.append(repo)
                continue

            rpc = urlfetch.create_rpc()
            url = '/'.join([GH_URL, 'orgs', orgname, 'repos?per_page=100'])
            urlfetch.set_default_fetch_deadline(60)
            urlfetch.make_fetch_call(rpc, url, headers=headers)

            repos[repo] = rpc

            # Wait 0.1 seconds to avoid GitHub abuse triggers
#            time.sleep(0.1)

        for repo in repos:
            rpc = repos[repo]
            result = rpc.get_result()
            content = json.loads(result.content)
            s = 'REPOCHECKER Version: %s' % REPOCHECKER_VERSION
            s += '\nGot {0} repos for {1}'.format(len(content), repo[0])
            logging.info(s)
            repo_list = [x['name'] for x in content]
            if repo_list is None or repo[1] not in repo_list:
                self.failed_repos.append(repo)

        return

    def get_all_repos(self):
        """Extract a list of all orgnames and reponames from Carto."""
        query = "select github_orgname, github_reponame\
                 from resource_staging\
                 where ipt is true and networks like '%VertNet%';"

        all_repos = carto_query(query)
        s = 'REPOCHECKER Version: %s' % REPOCHECKER_VERSION
        s += '\nGot {0} repos currently in Carto'.format(len(all_repos))
        logging.info(s)

        result = []
        for repo in all_repos:
            result.append((repo['github_orgname'], repo['github_reponame']))

        return result
