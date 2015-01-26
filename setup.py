from setuptools import setup

from app.main import fmt_version

setup(
    name = 'herd',
    version = fmt_version("short")
    packages = ['app'],
    setup_requires = ['fabric'],
    description = 'Herd Enables Rapid Deployment. A devops management tool.',
    author = 'Jesse B Miller',
    author_email = 'Jesse.Miller@adops.com',
    classifiers = [],
    url = 'https://github.com/OAODEV/herd',
    entry_points = {
        'console_scripts': ['herd = app.main:main'],
    }
)
