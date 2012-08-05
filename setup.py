from distutils.core import setup

setup(
        name='TactileGraphicsWorker',
        version='0.1.dev001',
        author='Marty McGuire',
        author_email='robert.m.mcguire@gmail.com',
        packages=['tactilegraphics', 'tactilegraphics.test'],
        scripts=['bin/tg_finished_job_worker.py',
                 'bin/tg_imap_worker.py',
                 'bin/tg_queue_worker.py'],
        url='https://github.com/The-PaD/TactileGraphicsWorker',
        license='LICENSE.txt',
        description='Scripts and workers for processing images into 3D models',
        long_description=open('README.txt').read(),
        install_requires=[
                    "CouchDB == 0.8",
                    "boto == 2.2.2",
                    "Jinja2 == 2.6",
                ],
)
