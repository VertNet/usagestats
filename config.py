from google.appengine.api import modules

MODULE_NAME = "tools-usagestats"
MODULE = modules.get_hostname(module=MODULE_NAME).replace("prod.", "")

# External API URLs and configs

# CartoDB
CDB_URL = "https://vertnet.cartodb.com/api/v2/sql"

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
URI_BASE = "/parser/dev/"
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
EMAIL_SENDER = "VertNet Tools - Usage Stats <javier.otegui@gmail.com>"
EMAIL_RECIPIENT = "Javier Otegui <javier.otegui@gmail.com>"
EMAIL_ADMINS = [
    "javier.otegui@gmail.com",
    "dbloom@vertnet.org",
    "larussell@vertnet.org",
    "tuco@berkeley.edu"
]
