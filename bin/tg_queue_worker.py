from tactilegraphics.logger import *
from boto.sqs.connection import SQSConnection
from boto.s3.connection import S3Connection
import ConfigParser, os
import json
import tempfile
import re
import subprocess
import time

# Set up logging
logger = TGLogger.set_logger('tg_queue_worker')
logger.info("Worker started.")

# Set up global objects
config = ConfigParser.ConfigParser()
config.read([os.path.expanduser('~/tactile_graphics.cfg'), os.path.expanduser('~/.tactile_graphics.cfg')])
sqs_conn = SQSConnection(config.get('aws','AWS_ACCESS_KEY_ID'),
                         config.get('aws','AWS_SECRET_ACCESS_KEY'))
job_queue = sqs_conn.get_queue(config.get('tg','TG_WORK_QUEUE'))
s3_conn = S3Connection(config.get('aws','AWS_ACCESS_KEY_ID'),
                       config.get('aws','AWS_SECRET_ACCESS_KEY'))

# Functions that get things done
def get_bucket_and_key_from_arn(url):
    m = re.search('^arn:aws:s3:::([^/]*)/(.*)$', url)
    if(m is None):
        return (None, None)
    bucket_name = m.group(1)
    key_name = m.group(2)
    return (bucket_name, key_name)

def get_s3_key_from_url(url):
    bucket_name, key_name = get_bucket_and_key_from_arn(url)
    if((bucket_name is None) or (key_name is None)):
        raise Exception("Don't know how to handle url: {0}".format(url))
    bucket = s3_conn.get_bucket(bucket_name)
    return bucket.get_key(key_name)

def fetch_source_file(src_url, workdir):
    remote_file = get_s3_key_from_url(src_url)
    if(remote_file is None):
        raise Exception("Could not find source file {0}".format(src_url))
    tmpf = open(os.path.join(workdir, os.path.basename(src_url)), "wb")
    remote_file.get_contents_to_file(tmpf)
    tmpf.close()
    return tmpf.name

def run_cmd(args, output_filename):
    logger.info(' '.join(args))
    start_time = time.time()
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout_data, stderr_data = process.communicate()
    stop_time = time.time()
    elapsed_time = stop_time - start_time
    exit_status = process.returncode
    logger.info("Command finished in %s seconds with status %s", elapsed_time, exit_status)
    return {
        'command': args,
        'exit_status': exit_status,
        'elapsed_time': elapsed_time,
        'output_file': output_filename,
        'stdout': stdout_data,
        'stderr': stderr_data
    }

def run_sikuli_cmd(img_filename):
    output_filename = "{0}.scad".format(img_filename)
    args = ['java',
            '-cp', config.get('tg','TG_CLASSPATH'),
            'org.sikuli.makerbot.Main',
            '-input', img_filename,
            '-output', output_filename
            ]
    return run_cmd(args, output_filename)

def run_openscad_cmd(scad_filename):
    output_filename = "{0}.stl".format(scad_filename)
    args = ['openscad',
            '-o', output_filename,
            scad_filename
           ]
    return run_cmd(args, output_filename)

def output_file_type_from_cmd_result(result):
    cmd_type_lookup = {
        'java': 'application/openscad',
        'openscad': 'application/sla'
    }
    return cmd_type_lookup[result['command'][0]]

def upload_result_files(target_dir, cmd_results):
    """Uploads output files from successful commands to S3.
       Also replaces the 'output_file' path in the command result
       with the arn:aws:s3:::... url for the newly created S3 file.
       Also, deletes the original files."""
    bucket_name, prefix = get_bucket_and_key_from_arn(target_dir)
    bucket = s3_conn.get_bucket(bucket_name)
    upload_results = []
    for cmd_result in cmd_results:
        if(cmd_result['exit_status'] == 0):
            filename = os.path.basename(cmd_result['output_file'])
            key_name = "{0}/{1}".format(prefix, filename)
            key = bucket.new_key(key_name)
            key.set_contents_from_file(open(cmd_result['output_file']))
            os.unlink(cmd_result['output_file'])
            arn = "arn:aws:s3:::{0}/{1}".format(bucket_name, key_name)
            cmd_result['output_file'] = arn
            upload_results.append({
                'type': output_file_type_from_cmd_result(cmd_result),
                'url': arn
            })
    return upload_results

def build_job_response(request, upload_files, log):
    return {
        'request': request,
        'upload_files': upload_files,
        'log': log
    }

def get_queue_from_arn(arn):
    """e.g. 'arn:aws:sqs:us-east-1:103653513881:tg-finished'"""
    m = re.search('^arn:aws:sqs:([^:]*):([^:]*):(.*)$', arn)
    if(m is None):
        return None
    region = m.group(1)
    aws_account_num = m.group(2)
    queue_name = m.group(3)
    return sqs_conn.get_queue(queue_name)

def send_notification(target, response):
    queue = get_queue_from_arn(target)
    if(queue is None):
        raise Exception("Don't know how to notify: {0}".format(target))
    logger.info("Notifying {0}".format(target))
    notify_msg = queue.new_message(json.dumps(response))
    queue.write(notify_msg)

def handle_job(job_data):
    logger.info("Processing job %s", job_data['_id'])
    cmd_results = []
    workdir = tempfile.mkdtemp()
    input_filename = fetch_source_file(job_data['source'], workdir)
    logger.info("Downloaded image to {0}".format(input_filename))
    sikuli_result = run_sikuli_cmd(input_filename)
    cmd_results.append(sikuli_result)
    if(sikuli_result['exit_status'] == 0):
        openscad_result = run_openscad_cmd(sikuli_result['output_file'])
        cmd_results.append(openscad_result)
    upload_files = upload_result_files(data['output_dir'], cmd_results)
    response = build_job_response(job_data, upload_files, cmd_results)
    for notification in job_data['notifications']:
        send_notification(notification, response)
    os.unlink(input_filename)
    os.rmdir(workdir)

# Do things
msg = job_queue.read()
if msg is None:
    logger.info("No jobs")
else:
    data = json.loads(msg.get_body())
    handle_job(data)
    msg.delete()
