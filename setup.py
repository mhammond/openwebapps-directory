from setuptools import setup, find_packages

version = '0.1'

setup(name='openwebapps-directory',
      version=version,
      description="A simple reference implementation of an Open Web Application directory",
      long_description="""\
This implements a simple directory of 'Open Web Applications'.
""",
      keywords='wsgi openwebapps',
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
          'DevAuth',
      ],
      entry_points="""
      [paste.app_factory]
      main = directory.configure:make_app
      """,
      )
