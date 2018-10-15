# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = '@tucotuco'
__contributors__ = "Javier Otegui, John Wieczorek"
__copyright__ = "Copyright 2018 vertnet.org"
__version__ = "WatchChecker.py 2018-10-15T10:46-03:00"
WATCHCHECKER_VERSION=__version__

import time
import json
import logging

from google.appengine.api import urlfetch, mail
import webapp2

from config import *
from util import apikey, carto_query

class WatchChecker(webapp2.RequestHandler):
    def post(self):
        self.get()

    def get(self, watcher):
        self.response.headers['Content-Type'] = 'application/json'
        if watcher is None or len(watcher) == 0:
            s = 'WatchChecker Version: %s' % WATCHCHECKER_VERSION
            s += '\nNo GitHub user name provided as watcher to check.'
            logging.info(s)
            watcher = 'tucotuco'
        self.watcher = watcher

        s = 'WatchChecker Version: %s' % WATCHCHECKER_VERSION
        s += '\nChecking which GitHub repositories in Carto are not being watched '
        s += 'by GitHub user %s.' % watcher
        logging.info(s)

        self.failed_repos = []
        self.check_failed_repos()

        res = {
            'result': None
        }

        if len(self.failed_repos) > 0:
            s = 'WatchChecker Version: %s' % WATCHCHECKER_VERSION
            s += '\nThere are %s repositories ' % len(self.failed_repos)
            s += 'not being watched by %s.' % watcher
            logging.warning(s)
            res['message'] = s
            res['unwatched_repos'] = self.failed_repos
            res['repo_count']=len(self.failed_repos)
            res['result'] = "warning"

#             error_msg = "\n".join([", ".join(x) for x in self.failed_repos])
#             mail.send_mail(
#                 sender=EMAIL_SENDER,
#                 to=EMAIL_ADMINS,
#                 subject="Resource watcher found unwatched repos",
#                 body="""
# Hey there,
# 
# This is an automatic message sent by the Watch Checker tool
# to inform you that the script found {0} name combinations of github_orgname and
# github_reponame in the VertNet Carto resource_staging table that are not being 
# watched on GitHub by {1}:
# 
# {2}
# 
# Please, watch the repositories in GitHub and then go to 
# {3} to restart the process.
# 
# Thank you!
# """.format(len(self.failed_repos), self.watcher, error_msg, "http://%s/" % MODULE))

        else:
            s = 'WatchChecker Version: %s' % WATCHCHECKER_VERSION
            s += '\nThe repository watch checker was successful '
            s += '- no unwatched repositories found.'
            logging.info(s)

            res['result'] = "success"
            res['message'] = s

        self.response.write(json.dumps(res))
        return

    def check_failed_repos(self):
        """Check repository watchers on GitHub."""

        # Get all of the repositories from Carto
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

            # API URL https://api.github.com/repos/[orgname]/[reponame]/subscribers
            rpc = urlfetch.create_rpc()
            url = '/'.join([GH_URL, 'repos', orgname, reponame, 'subscribers'])
            urlfetch.set_default_fetch_deadline(60)
            urlfetch.make_fetch_call(rpc, url, headers=headers)

            repos[repo] = rpc

            # Wait 0.1 second to avoid GitHub abuse triggers
            time.sleep(0.1)

        # temporarily hard code the watcher to look for
        for repo in repos:
            rpc = repos[repo]
            result = rpc.get_result()
            content = json.loads(result.content)
            s = 'WatchChecker Version: %s' % WATCHCHECKER_VERSION
            s += '\nGot {0} watchers for {1}'.format(len(content), repo[0])
            logging.info(s)
            watcher_list = [x['login'] for x in content]
            if watcher_list is None or self.watcher not in watcher_list:
                orgname = repo[0]
                reponame = repo[1]
                if orgname is None and reponame is None:
                    self.failed_repos.append(repo)
                else:
                    s = 'http://github.com/'
                    if orgname is not None:
                        s += '%s' % orgname
                    s += '/'
                    if reponame is not None:
                        s += '%s' % reponame
                    s += '/'
                    self.failed_repos.append(s)
        return

    def get_all_repos(self):
        """Extract a list of all orgnames and reponames from Carto."""
        query = "select github_orgname, github_reponame\
                 from resource_staging\
                 where ipt is true and networks like '%VertNet%';"

        all_repos = carto_query(query)
        s = 'WatchChecker Version: %s' % WATCHCHECKER_VERSION
        s += '\nGot {0} repos currently in Carto'.format(len(all_repos))
        logging.info(s)

        result = []
        for repo in all_repos:
            result.append((repo['github_orgname'], repo['github_reponame']))

        return result
