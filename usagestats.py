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
__version__ = "usagestats.py 2018-10-14T20:57-03:00"

from admin.parser.InitExtraction import InitExtraction
from admin.parser.GetEvents import GetEvents
from admin.parser.ProcessEvents import ProcessEvents
from admin.parser.GitHubStore import GitHubStore
from admin.parser.GitHubIssue import GitHubIssue
from admin.setup.DatasetsSetup import DatasetsSetup
from admin.tools.Status import Status
from admin.tools.PeriodStatus import PeriodStatus
from admin.tools.RepoChecker import RepoChecker
from admin.tools.WatchChecker import WatchChecker
from admin.tools.EmailTester import EmailTester
from admin.tools.EntityCleaner import EntityCleaner
from viewer.DatasetViewer import DatasetViewer
from viewer.ReportViewer import ReportViewer, TXTReportViewer, JSONReportViewer
import webapp2

# Administrative processes
admin = webapp2.WSGIApplication([

    # Report generator
    ('/admin/parser/init', InitExtraction),
    ('/admin/parser/get_events', GetEvents),
    ('/admin/parser/process_events', ProcessEvents),
    ('/admin/parser/github_store', GitHubStore),
    ('/admin/parser/github_issue', GitHubIssue),

    # Accessory tools
    ('/admin/setup/datasets', DatasetsSetup),
    ('/admin/status', Status),
    webapp2.Route(r'/admin/status/period/<period>', handler=PeriodStatus),
    ('/admin/tools/repo_checker', RepoChecker),
    ('/admin/tools/watch_checker', WatchChecker),
    webapp2.Route(r'/admin/tools/watch_checker/watcher/<watcher>', handler=WatchChecker),
    ('/admin/tools/email_tester', EmailTester),
    ('/admin/tools/entity_cleaner', EntityCleaner),

], debug=True)


# Public processes
app = webapp2.WSGIApplication([

    # Report viewer routes
    webapp2.Route(r'/reports/<gbifdatasetid>/',
                  handler=DatasetViewer),
    webapp2.Route(r'/reports/<gbifdatasetid>/<period>/',
                  handler=ReportViewer),
    webapp2.Route(r'/reports/<gbifdatasetid>/<period>/json',
                  handler=JSONReportViewer),
    webapp2.Route(r'/reports/<gbifdatasetid>/<period>/txt',
                  handler=TXTReportViewer),

], debug=True)
