#!/usr/bin/env python

import codecs

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

def get_requirements(req_file='requirements.txt'):
    with open(req_file) as fp:
        return [x.strip() for x in fp.read().split('\n') if not x.startswith('#')]

with codecs.open("README.md", encoding="utf-8") as fp:
    long_description = fp.read()

setup(
    name='sentry-opsgenie',
    version='1.0',
    author='Kumarappan Arumugam',
    author_email='kumarappan.ar@gmail.com',
    description='A sentry notification integration with opsgenie',
    long_description=long_description,
    url='https://github.com/kumarappan-arumugam/sentry-opsgenie',
    packages=find_packages(),
    install_requires=get_requirements(),
    include_package_data=True,
    classifiers=[
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: Software Development'
    ],
    keywords=['Sentry', 'OpsGenie', 'Alerts', 'SentryPlugin'],
    entry_points={
        'sentry.apps': [
            'sentry_opsgenie = sentry_opsgenie',
        ],
        'sentry.integrations': [
            'sentry_opsgenie = sentry_opsgenie.integration:OpsgenieIntegrationProvider',
        ],
    },
)
