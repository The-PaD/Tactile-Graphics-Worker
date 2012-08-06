"""
Allows a worker to limit itself to one running copy at a time
by checking existence of a file containing the PID of the
currently running process.

Usage:

    assert_pid_lock('worker_name', logger)
    # do stuff
    release_pid_lock('worker_name')
"""
import os, sys

def assert_pid_lock(name, logger):
    pid_file = "/tmp/%s.pid" % name
    if os.access(pid_file, os.F_OK):
        pfh = open(pid_file, "r")
        pfh.seek(0)
        pid = pfh.readline()
        pfh.close()
        if(os.path.exists("/proc/%s" % pid)):
            logger.warn("%s already running with PID %s. Exiting.", name, pid)
            sys.exit(0)
        else:
            logger.warn("Stale PID %s for %s. Overwriting it.", pid, name)
            os.unlink(pid_file)
    pfh = open(pid_file, "w")
    pfh.write("%s" % os.getpid())
    pfh.close()

def release_pid_lock(name):
    pid_file = "/tmp/%s.pid" % name
    os.unlink(pid_file)
