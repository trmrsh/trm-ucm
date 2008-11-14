from ez_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages
from distutils.core import Extension
import os
import numpy

"""Setup script for Python module for ucm files"""

setup(name='trm.ucm',
      namespace_packages = ['trm'],
      version='0.1',
      package_dir = {'trm.ucm' : os.path.join('trm', 'ucm')},
      packages = find_packages(),
      scripts=['scripts/pucm', 'scripts/snorm'],
      zip_safe = False,

      author='Tom Marsh',
      description="Python module for reading/writing ucm files",
      author_email='t.r.marsh@warwick.ac.uk',
      url='http://www.astro.warwick.ac.uk/',

      )

