from distutils.core import setup, Extension
import os

"""Setup script for Python module for ucm files"""

setup(name='trm.ucm',
      version='0.3',
      packages = ['trm', 'trm.ucm'],
      scripts=['scripts/pucm', 'scripts/snorm'],

      author='Tom Marsh',
      description="Python module for reading/writing ucm files",
      author_email='t.r.marsh@warwick.ac.uk',
      url='http://www.astro.warwick.ac.uk/',

      )

