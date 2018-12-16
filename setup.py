import os
import re
import sys
from setuptools import setup


install_requires = []


if sys.version_info < (3, 5, 3):
    raise RuntimeError('aiorwlock requires Python 3.5.3+')


def read(f):
    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()


def read_version():
    regexp = re.compile(r"^__version__\W*=\W*'([\d.abrc]+)'")
    init_py = os.path.join(os.path.dirname(__file__),
                           'aiorwlock', '__init__.py')
    with open(init_py) as f:
        for line in f:
            match = regexp.match(line)
            if match is not None:
                return match.group(1)
        else:
            raise RuntimeError('Cannot find version in aiorwlock/__init__.py')


classifiers = [
    'License :: OSI Approved :: Apache Software License',
    'Intended Audience :: Developers',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Operating System :: OS Independent',
    'Development Status :: 4 - Beta',
    'Framework :: AsyncIO',
]


setup(name='aiorwlock',
      version=read_version(),
      description=('Read write lock for asyncio.'),
      long_description='\n\n'.join((read('README.rst'), read('CHANGES.rst'))),
      classifiers=classifiers,
      platforms=['POSIX'],
      author='Nikolay Novik',
      author_email='nickolainovik@gmail.com',
      url='https://github.com/aio-libs/aiorwlock',
      download_url='https://pypi.python.org/pypi/aiorwlock',
      license='Apache 2',
      packages=['aiorwlock'],
      install_requires=install_requires,
      keywords=['aiorwlock', 'lock', 'asyncio'],
      zip_safe=True,
      include_package_data=True)
