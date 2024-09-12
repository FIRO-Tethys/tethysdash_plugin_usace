from setuptools import setup, find_packages
import versioneer

INSTALL_REQUIRES = ['intake >=0.6.6', 'pandas', 'numpy', 'plotly', 'requests']

setup(
    name='aquainsight_plugin_usace',
    version="0.0.1",
    cmdclass=versioneer.get_cmdclass(),
    description='xarray plugins for Intake',
    url='https://github.com/intake/intake-xarray',
    maintainer='Martin Durant',
    maintainer_email='mdurant@anaconda.com',
    license='BSD',
    py_modules=['intake_xarray'],
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