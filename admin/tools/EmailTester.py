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
__version__ = "EmailTester.py 2018-10-09T16:06-03:00"
EMAILTESTER_VERSION=__version__

from google.appengine.api import mail
import webapp2
from config import *

class EmailTester(webapp2.RequestHandler):
    def get(self):
        self.period = "TESTING"

        ret = mail.send_mail(
            sender=EMAIL_SENDER,
            to=EMAIL_RECIPIENT,
            subject="Usage reports for period %s" % self.period,
            body="""
Hey there!

Just a brief note to let you know the extraction of %s stats has successfully
finished, with no GitHub processes launched.

Congrats!
""" % self.period)
        self.response.write(ret)
        return
