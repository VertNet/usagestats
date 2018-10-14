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
__version__ = "EmailTester.py 2018-10-12T11:36-03:00"

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

Just a test to let you know the EmailTester is working. %s.

Congrats!
""" % self.period)
        self.response.write(ret)
        return
