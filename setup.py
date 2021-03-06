from setuptools import setup

with open('Version', 'r') as versionfile:
    v = versionfile.read()

setup(
    name='herd',
    version=v,
    packages=['app'],
    dependency_links=[
        "https://github.com/OAODEV/python-gnupg/tarball/master#egg=gnupg",
    ],
    install_requires=[
        'fabric',
        'gnupg',
        'psycopg2',
        'sqlalchemy',
        ],
    description='Herd Enables Rapid Deployment. A devops management tool.',
    author='Jesse B Miller',
    author_email='Jesse.Miller@adops.com',
    classifiers=[],
    url='https://github.com/OAODEV/herd',
    entry_points={
        'console_scripts': ['herd = app.main:main'],
    }
)
