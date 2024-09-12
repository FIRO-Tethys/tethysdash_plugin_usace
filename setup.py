from setuptools import setup, find_packages

INSTALL_REQUIRES = ['intake >=0.6.6', 'pandas', 'numpy', 'plotly', 'requests']

setup(
    name='aquainsight_plugin_usace',
    version="0.0.1",
    description='usace visualization plugins for aquainsight',
    url='https://github.com/FIRO-Tethys/aquainsight_plugin_usace',
    maintainer='Corey Krewson',
    maintainer_email='ckrewson@aquaveo.com',
    license='BSD',
    py_modules=['aquainsight_plugin_usace'],
    packages=find_packages(),
    entry_points={
        'intake.drivers': [
            'usace_time_series = usace_visualizations.time_series:TimeSeries',
        ]
    },
    package_data={'': ['*.csv', '*.yml', '*.html']},
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    zip_safe=False, )