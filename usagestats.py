#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from datasets import DatasetsSetupHandler

from reports_viewer import *

from report_generator import *
from report_tasks import *

from dev import *

__author__ = 'jotegui'


class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.redirect("/periods")

app = webapp2.WSGIApplication([
    # Dev and testing
    # ('/test', TestHandler),
    # ('/dev_setup', DevSetup),

    # Main handler
    webapp2.Route('/', handler=MainHandler),

    # Setup routes
    webapp2.Route('/setup_datasets', handler=DatasetsSetupHandler, name='setup_datasets'),

    # Report viewer routes
    webapp2.Route('/reports', handler=ReportListHandler),
    webapp2.Route(r'/reports/sha/<sha>/', handler=StoreReportHandler, name='process_report'),
    webapp2.Route(r'/reports/<gbifdatasetid>/', handler=DatasetHandler, name='dataset'),
    webapp2.Route(r'/reports/<gbifdatasetid>/<period>/', handler=ReportHandler, name='report'),
    webapp2.Route(r'/reports/<gbifdatasetid>/<period>/json', handler=JSONReportHandler, name='report_json'),
    webapp2.Route(r'/reports/<gbifdatasetid>/<period>/txt', handler=TXTReportHandler, name='report_txt'),

    # Report generator status routes
    webapp2.Route('/periods', handler=PeriodListHandler),
    webapp2.Route('/status', handler=StatusHandler),
    webapp2.Route(r'/status/period/<period>', handler=PeriodStatusHandler),

    # Generator tasks
    webapp2.Route(r'/parser/<period>', handler=ProcessPeriod),
    webapp2.Route(r'/parser/nogithub/<period>', handler=ProcessPeriodNoGithub),
    # webapp2.Route(r'/parser/geteventslist/', handler=GetEventsList),
    # webapp2.Route(r'/parser/parseeventslist/', handler=ParseEventList),
    # webapp2.Route(r'/parser/processevents/', handler=ProcessEvents),

], debug=True)
