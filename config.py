#!/usr/bin/env python
# -*- coding: utf-8 -*-
# The line above is to signify that the script contains utf-8 encoded characters.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = "Javier Otegui"
__contributors__ = "Javier Otegui, John Wieczorek"
__copyright__ = "Copyright 2018 vertnet.org"
__version__ = "config.py 2018-10-09T16:02-03:00"
CONFIG_VERSION=__version__

from google.appengine.api import modules

MODULE_NAME = "tools-usagestats"
MODULE = modules.get_hostname(module=MODULE_NAME).replace("prod.", "")

# External API URLs and configs

# Carto
CDB_URL = "https://vertnet.carto.com/api/v2/sql"
CDB_TABLE = "query_log_master"

# Geonames
GNM_URL = "http://api.geonames.org/countryCodeJSON"

# GitHub
GH_URL = "https://api.github.com"
GH_REPOS = GH_URL + "/repos"
GH_COMMITTER = {
    'name': 'VertNet',
    'email': 'vertnetinfo@vertnet.org'
}

# URIs, relative to app root
URI_BASE = "/admin/parser/"
URI_INIT = URI_BASE + "init"
URI_GET_EVENTS = URI_BASE + "get_events"
URI_PROCESS_EVENTS = URI_BASE + "process_events"
URI_GITHUB_STORE = URI_BASE + "github_store"
URI_GITHUB_ISSUE = URI_BASE + "github_issue"

# URLs
URL_BASE = "http://" + MODULE
URL_INIT = URL_BASE + URI_INIT
URL_GET_EVENTS = URL_BASE + URI_GET_EVENTS
URL_PROCESS_EVENTS = URL_BASE + URI_PROCESS_EVENTS
URL_GITHUB_STORE = URL_BASE + URI_GITHUB_STORE
URL_GITHUB_ISSUE = URL_BASE + URI_GITHUB_ISSUE

# Other module-wide variables
QUEUENAME = "usagestatsqueue"
EMAIL_SENDER = "VertNet Tools - Usage Stats <vertnetinfo@vertnet.org>"
EMAIL_RECIPIENT = "John Wieczorek <tuco@berkeley.edu>"
EMAIL_ADMINS = [
    "dbloom@vertnet.org",
    "tuco@berkeley.edu"
]
