from tactilegraphics.inbox import *
from boto.sqs.connection import SQSConnection
from boto.s3.connection import S3Connection
from boto.s3.key import Key
import couchdb.client
import uuid
import mimetypes
import json
import ConfigParser, os

# Set up global objects
config = ConfigParser.ConfigParser()
config.read([os.path.expanduser('~/tactile_graphics.cfg'), os.path.expanduser('~/.tactile_graphics.cfg')])

sqs_conn = SQSConnection(config.get('aws','AWS_ACCESS_KEY_ID'),
                         config.get('aws','AWS_SECRET_ACCESS_KEY'))
queue = sqs_conn.get_queue(config.get('tg','TG_WORK_QUEUE'))
finished_queue = sqs_conn.get_queue(config.get('tg','TG_FINISHED_QUEUE'))

s3_conn = S3Connection(config.get('aws','AWS_ACCESS_KEY_ID'),
                         config.get('aws','AWS_SECRET_ACCESS_KEY'))
bucket = s3_conn.get_bucket(config.get('tg','TG_FILE_BUCKET'))

couch = couchdb.client.Server()
db = couch[config.get('tg','TG_COUCH_DB')]

# Functions that get things done
def save_part(msg_id, content_type, data):
    path = "message-parts/{0}/{1}".format(msg_id, uuid.uuid4().hex)
    print "saving {0} part to {1}".format(content_type, path)
    k = bucket.new_key(path)
    k.set_contents_from_string(data, headers={'Content-Type': content_type})
    k.make_public()
    return "arn:aws:s3:::{0}/{1}".format(bucket.name, path)

def create_job(msg_id, part_data):
    if (part_data['content-type'].startswith('image/')):
        path = "arn:aws:s3:::{0}/job-output/{1}/{2}".format(bucket.name, msg_id, uuid.uuid4().hex)
        job_data = {
            'type': 'job',
            'status': 'processing',
            'msg_id': msg_id,
            'source': part_data['uri'],
            'output_dir': path,
            'notifications': [
                finished_queue.get_attributes()['QueueArn']
            ]
        }
        doc_id, doc_rev = db.save(job_data)
        job_msg = queue.new_message(json.dumps(job_data))
        queue.write(job_msg)

def create_jobs(msg_data):
    parts = msg_data['request']['parts']
    for part in parts:
        create_job(msg_data['msg_id'], part)

def handle_email(msg):
    msg_id = uuid.uuid4().hex
    parts = []
    request = {
        'headers': msg.items(),
        'parts': parts
    }
    msg_data = {
        'type': 'message',
        'status': 'new',
        'request': request,
        'msg_id': msg_id
    }
    for part in msg.walk():
        if (not part.get_content_type().startswith("multipart/mixed")):
            parts.append({
                'content-type': part.get_content_type(),
                'headers': part.items(),
                'uri': save_part(msg_id, part.get_content_type(),
                                 part.get_payload(decode=True))
            })
            print part.get_content_type()
    doc_id, doc_rev = db.save(msg_data)
    create_jobs(msg_data)

# Do things
inbox = TGInbox(config.get('email','IMAP_SERVER'),
                config.get('email','IMAP_PORT'),
                config.get('email','IMAP_USER'),
                config.get('email','IMAP_PASSWORD'))
print inbox.unreadcount
for msg in inbox:
    handle_email(msg)
