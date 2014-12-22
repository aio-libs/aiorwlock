import os
import re
import sys
from setuptools import setup, find_packages


install_requires = []

PY_VER = sys.version_info

if PY_VER >= (3, 4):
    pass
elif PY_VER >= (3, 3):
    install_requires.append('asyncio')
else:
    raise RuntimeError("aiorwlock doesn't suppport Python earllier than 3.3")


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
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'Operating System :: OS Independent',
    'Development Status :: 2 - Pre-Alpha',
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
      packages=find_packages(),
      install_requires=install_requires,
      include_package_data = True)
