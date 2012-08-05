================
Tactile Graphics
================

Classes and services for processing images received via email
into 3D files in STL format, suitable for 3D printing.

Requirements
============

* Amazon S3 bucket
* Amazon SQS queues
* sikuli-makerbot-1.0-jar-with-dependencies.jar
* A server to run things on
  * CouchDB
  * Python
  * Java
  * OpenSCAD

Future Requirements
-------------------

Better documentation. :P

Setup
=====

Simplest way to set up for development/deployment:

    $ git clone git@github.com:The-PaD/TactileGraphicsWorker.git
    $ cd TactileGraphicsWorker
    $ sudo pip install -e .
    $ cp docs/tactile_graphics_cfg_example.txt ~/tactile_graphics.cfg
    $ cp docs/.tactile_graphics_cfg_example.txt ~/.tactile_graphics.cfg

Edit ~/.tactile_graphics.cfg to match your configuration.

Log Dir
-------

Create a logs directory in the home directory of the user that will "own"
the Tactile Graphics worker processes::

    $ cd $HOME
    $ mkdir logs

Cron Jobs
---------

You should create the following crontab entries for the user that will "own"
the Tactile Graphics worker processes::

    * * * * * (cd $HOME && imap_worker.py  >> logs/imap_worker.log)
    * * * * * (cd $HOME && queue_worker.py  >> logs/queue_worker.log)
    * * * * * (cd $HOME && finished_job_worker.py  >> logs/finished_job_worker.log)

Contributors
============

* Marty McGuire <robert.m.mcguire@gmail.com>
