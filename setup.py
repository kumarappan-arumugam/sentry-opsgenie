#!/usr/bin/env python
import codecs
# import pip

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

# try: # for pip >= 10
#     from pip._internal.req import parse_requirements
#     from pip._internal.download import PipSession
# except ImportError: # for pip <= 9.0.3
#     from pip.req import parse_requirements
#     from pip.download import PipSession

# links = []
# requires = []

# try:
#     requirements = [item for item in parse_requirements('requirements.txt')]
# except:
#     # new versions of pip requires a session
#     requirements = [item for item in parse_requirements(
#         'requirements.txt', session=PipSession()
#     )]

# for item in requirements:
#     # we want to handle package names and also repo urls
#     if getattr(item, 'url', None):  # older pip has url
#         links.append(str(item.url))
#     if getattr(item, 'link', None): # newer pip has link
#         links.append(str(item.link))
#     if item.req:
#         requires.append(str(item.req))

def get_requirements(req_file='requirements.txt'):
    with open(req_file) as fp:
        return [x.strip() for x in fp.read().split('\n') if not x.startswith('#')]

with codecs.open("README.md", encoding="utf-8") as fp:
    long_description = fp.read()

setup(
    name='sentry-opsgenie',
    version='0.0.1',
    author='Kumarappan Arumugam',
    author_email='kumarappan.ar@gmail.com',
    description='A sentry notification integration with opsgenie',
    long_description=long_description,
    url='https://github.com/kumarappan-arumugam/sentry-opsgenie',
    packages=find_packages(),
    install_requires=get_requirements(),
    include_package_data=True,
    # dependency_links=links,
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
            'sentry_opsgenie = sentry_opsgenie.integrations:OpsgenieIntegration',
        ],
    },
)
