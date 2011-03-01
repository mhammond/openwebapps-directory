from setuptools import setup, find_packages

version = '0.1'

setup(name='openwebapps-directory',
      version=version,
      description="A simple reference implementation of an Open Web Application directory",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Ian Bicking',
      author_email='ianb@mozilla.com',
      url='http://apps.mozillalabs.com',
      license='MPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'WebOb',
          'Jinja2',
          'SQLAlchemy',
          'Routes',
      ],
      entry_points="""
      [paste.app_factory]
      main = directory.wsgiapp:make_app
      """,
      )
