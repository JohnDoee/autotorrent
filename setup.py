#!/usr/bin/env python

from setuptools import setup

def read_description():
    import os
    path = os.path.join(os.path.dirname(__file__), 'README.rst')
    try:
        with open(path) as f:
            return f.read()
    except:
        return 'No description found'

setup(
    name='autotorrent',
    version='1.6.1',
    description='AutoTorrent allows easy cross-seeding',
    long_description=read_description(),
    author='Anders Jensen',
    author_email='johndoee+autotorrent@tidalstream.org',
    maintainer='John Doee',
    url='https://github.com/JohnDoee/autotorrent',
    packages=['autotorrent', 'autotorrent.clients'],
    install_requires=['six', 'deluge-client', 'requests'],
    license='MIT',
    package_data={'autotorrent': ['autotorrent.conf.dist']},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: BSD',
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX :: Other',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Communications :: File Sharing',
    ],
    entry_points={ 'console_scripts': [
        'autotorrent = autotorrent.cmd:commandline_handler',
    ]},
)
