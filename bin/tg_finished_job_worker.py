"""
A worker that pulls from the finished jobs queue.
Reponsible for:
 * updating a job's state in the db
 * updating the job's message in the db
 * sending out emails when all jobs for a message are complete.
"""

from tactilegraphics.response import *
from boto.sqs.connection import SQSConnection
from boto.s3.connection import S3Connection
import couchdb.client
import ConfigParser, os
import json
import tempfile
import re
import pprint
import subprocess
import time

# Set up global objects
config = ConfigParser.ConfigParser()
config.read([os.path.expanduser('~/tactile_graphics.cfg'), os.path.expanduser('~/.tactile_graphics.cfg')])

sqs_conn = SQSConnection(config.get('aws','AWS_ACCESS_KEY_ID'),
                         config.get('aws','AWS_SECRET_ACCESS_KEY'))
job_queue = sqs_conn.get_queue(config.get('tg','TG_FINISHED_QUEUE'))

s3_conn = S3Connection(config.get('aws','AWS_ACCESS_KEY_ID'),
                       config.get('aws','AWS_SECRET_ACCESS_KEY'))

couch = couchdb.client.Server()
db = couch[config.get('tg', 'TG_COUCH_DB')]

# Functions that get things done
def fetch_job(finished_msg):
    """Given a finished job message, returns the job data stored in the db."""
    return db[finished_msg['request']['_id']]

def fetch_message_for_job(job):
    """Given a job from the db, returns the associated message from the db."""
    view_results = db.view('messages/by_msg_id')
    return list(view_results[job['msg_id']])[0].value

def get_status_from_msg(finished_msg):
    """Return a job status based on the finished job message.
    'complete' if the job created both output files successfully.
    'failed' otherwise.
    """
    if(len(finished_msg['upload_files']) == 2):
        return 'complete'
    else:
        return 'failed'

def get_results_dict_from_msg(finished_msg):
    """Transform message's upload_files data from format:
        [{"type": "sometype", "url': "someurl"}, ...] into
        {"sometype": "someurl"}
    """
    ret = {}
    for file_info in finished_msg['upload_files']:
        ret[file_info['type']] = file_info['url']
    return ret

def update_job(job, finished_msg):
    """Updates a job in the db based on the message about the finished job."""
    job['status'] = get_status_from_msg(finished_msg)
    job['results'] = get_results_dict_from_msg(finished_msg)
    job['tasks'] = finished_msg['log']
    db[job.id] = job

def fetch_jobs_for_message(message):
    """Return a list of jobs from the DB that belong to the given message."""
    results = db.view('jobs/by_msg_id')[message['msg_id']]
    return [row.value for row in results]

def check_all_jobs_complete(jobs):
    """Given a list of jobs from the DB, check that all are done processing."""
    for job in jobs:
        if(job['status'] == 'processing'):
            return False
    return True

def get_bucket_and_key_from_arn(url):
    m = re.search('^arn:aws:s3:::([^/]*)/(.*)$', url)
    if(m is None):
        return (None, None)
    bucket_name = m.group(1)
    key_name = m.group(2)
    return (bucket_name, key_name)

def make_job_file_public(url):
    """Set public-read ACL for url of the form:
    arn:aws:s3:::<bucket>/<key>
    """
    bucket_name, key_name = get_bucket_and_key_from_arn(url)
    bucket = s3_conn.get_bucket(bucket_name)
    key = bucket.get_key(key_name)
    key.set_canned_acl('public-read')

def make_job_files_public(jobs):
    """Given a list of jobs from the db, make their result files
    publicly readble.
    """
    for job in jobs:
        for mimetype, url in job['results'].iteritems():
            make_job_file_public(url)

def create_reply_message(message, jobs):
    return TGResponse(message,
                      jobs,
                      config.get('email','IMAP_USER'),
                      config.get('email','IMAP_PASSWORD'))

def send_response(response):
    response.send()

def update_message(message, response):
    message['status'] = 'complete'
    message['response'] = {
        'to': "%s <%s>" % (response.to_realname, response.to_addr),
        'subject': response.subject,
        'jobs': response.jobs,
        'body': response.html_content()
    }
    db[message['_id']] = message

def handle_job(finished_msg):
    """Process a finished job.

    @param dict finished_msg: 'request', 'upload_files', 'log'
    """
    job = fetch_job(finished_msg)
    message = fetch_message_for_job(job)

    update_job(job, finished_msg)
    jobs = fetch_jobs_for_message(message)
    if(check_all_jobs_complete(jobs)):
        make_job_files_public(jobs)
        response = create_reply_message(message, jobs)
        send_response(response)
        update_message(message, response)
        print "Response sent: %s" % response.subject
    else:
        print "still outstanding jobs. done for now.\n"

# Do things
if __name__ == '__main__':
    msg = job_queue.read(1)
    if msg is None:
        print "No jobs"
    else:
        data = json.loads(msg.get_body())
        handle_job(data)
        msg.delete()
