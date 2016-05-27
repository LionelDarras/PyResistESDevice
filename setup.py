# coding: utf8
'''
    PyResistESDevice
    ----------------

    Communication tools with an electro-static resistivimeter device
    developped by Metis Laboratory.

    :copyright: Copyright 2015 Lionel Darras and contributors, see AUTHORS.
    :license: GNU GPL v3.

'''
import re
import sys
import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

README = ''
CHANGES = ''
try:
    README = open(os.path.join(here, 'README.rst')).read()
    CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
except:
    pass

REQUIREMENTS = [
    'pylink',
    'argparse'
]

with open(os.path.join(os.path.dirname(__file__), 'pyresistesdevice',
                        '__init__.py')) as init_py:
    release = re.search("VERSION = '([^']+)'", init_py.read()).group(1)
# The short X.Y version.
version = release.rstrip('dev')

setup(
    name='PyResistESDevice',
    version=version,
    url='https://github.com/LionelDarras/PyResistESDevice',
    license='GNU GPL v3',
    description='Communication tools with an electro-static resistivimeter device developped by UMR7619-Metis Laboratory.',
    long_description=README + '\n\n' + CHANGES,
    author='Lionel Darras & Sebastien Flageul',
    author_email='lionel.darras@mom.fr',
    maintainer='Lionel Darras',
    maintainer_email='lionel.darras@mom.fr',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet',
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    packages=find_packages(),
    zip_safe=False,
    install_requires=REQUIREMENTS,
    entry_points={
        'console_scripts': [
            'pyresistesdevice = pyresistesdevice.__main__:main'
        ],
    },
)
