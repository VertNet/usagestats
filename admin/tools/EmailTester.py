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
