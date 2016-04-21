import json
import logging

from google.appengine.api import urlfetch, mail
import webapp2

from config import *
from util import apikey, cartodb_query

__author__ = '@jotegui'


class RepoChecker(webapp2.RequestHandler):
    def post(self):
        self.get()

    def get(self):
        self.response.headers['Content-Type'] = 'application/json'

        logging.info("Checking consistency of repository names"
                     " between CartoDB and GitHub.")

        self.failed_repos = []
        self.check_failed_repos()

        res = {
            'result': None
        }

        if len(self.failed_repos) > 0:
            res['failed_repos'] = self.failed_repos
            res['result'] = "error"
            logging.error("There were issues in the repository name matching.")

            error_msg = "\n".join([", ".join(x) for x in self.failed_repos])
            mail.send_mail(
                sender=EMAIL_SENDER,
                to=EMAIL_ADMINS,
                subject="Resource name checker failed",
                body="""
Hey there,

This is an automatic message sent by the Resource name checker tool
to inform you that the script found {0} name inconsistencies in some
repositories between CartoDB's resource_staging table and the name of
organization and/or repository on GitHub. These are the specific
repositories that failed (names as in CartoDB):

{1}

Please, fix them and then go to {2} to restart the process.

Thank you!
""".format(len(self.failed_repos), error_msg, "http://%s/" % MODULE))

        else:
            res['result'] = "success"
            logging.info("The consistency check could not find any issue.")

        self.response.write(json.dumps(res))
        return

    def check_failed_repos(self):
        """Check repository name consistency between CartoDB and GitHub."""

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
            url = '/'.join([GH_URL, 'orgs', orgname, 'repos'])
            urlfetch.set_default_fetch_deadline(60)
            urlfetch.make_fetch_call(rpc, url, headers=headers)

            repos[repo] = rpc

        for repo in repos:
            rpc = repos[repo]
            result = rpc.get_result()
            content = json.loads(result.content)
            logging.info("Got {0} repos for {1}".format(len(content), repo[0]))
            repo_list = [x['name'] for x in content]
            if repo_list is None or repo[1] not in repo_list:
                self.failed_repos.append(repo)

        return

    def get_all_repos(self):
        """Extract a list of all orgnames and reponames from CartoDB."""
        query = "select github_orgname, github_reponame\
                 from resource_staging\
                 where ipt is true and networks like '%VertNet%';"

        all_repos = cartodb_query(query)
        logging.info("Got {0} repos currently in CartoDB"
                     .format(len(all_repos)))

        result = []
        for repo in all_repos:
            result.append((repo['github_orgname'], repo['github_reponame']))

        return result
