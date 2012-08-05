import os
import inspect
import re
import smtplib
from email.mime.text import MIMEText
from email.utils import parseaddr
from jinja2 import Environment, FileSystemLoader

class TGResponse:
    """Handles sending response emails given a message
    and set of finished jobs."""

    to_addr = ''
    to_realname = ''
    subject = ''
    original_subject = ''

    def __init__(self, message, jobs, smtp_user, smtp_pass):
        self.message = message
        self.jobs = jobs
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.parse_recipient_info()
        self.set_subject()
        self.sort_jobs()

    def set_subject(self):
        self.original_subject = self.get_first_header('Subject')
        self.subject = "Re: %s" % (self.original_subject)

    def parse_recipient_info(self):
        from_addr = self.get_first_header('From')
        (self.to_realname, self.to_addr) = parseaddr(from_addr)

    def get_first_header(self, header_name):
        for header in self.message['request']['headers']:
            if(header[0] == header_name):
                return header[1]
        return None

    def sort_jobs(self):
        self.successful_jobs = []
        self.failed_jobs = []
        for job in self.jobs:
            if (job['status'] == 'complete'):
                self.successful_jobs.append(self.prep_success_job(job))
            else:
                self.failed_jobs.append(self.prep_failed_job(job))

    def prep_success_job(self, job):
        return {
            'image_file': self.translate_s3_url(job['source']),
            'stl_file':
            self.translate_s3_url(job['results']['application/sla']),
            'scad_file':
            self.translate_s3_url(job['results']['application/openscad'])
        }

    def prep_failed_job(self, job):
        return { 'image_file': self.translate_s3_url(job['source']) }

    def translate_s3_url(self, url):
        m = re.search('^arn:aws:s3:::([^/]*)/(.*)$', url)
        if(m is None):
            return None
        bucket_name = m.group(1)
        key_name = m.group(2)
        return "http://s3.amazonaws.com/%s/%s" % (bucket_name, key_name)

    def html_content(self):
        self_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
        template_dir = os.path.join(self_dir, 'templates')
        templates = Environment(loader=FileSystemLoader(template_dir))
        template = templates.get_template('html-email.phtml')
        return template.render(response=self)

    def send(self):
        msg = MIMEText(self.html_content(), 'html')
        msg['Subject'] = self.subject
        msg['From'] = "Tactile Graphics <%s>" % (self.smtp_user)
        msg['To'] = "%s <%s>" % (self.to_realname, self.to_addr)
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(self.smtp_user, self.smtp_pass)
        s.sendmail(msg['From'], msg['To'], msg.as_string())
        s.close()

