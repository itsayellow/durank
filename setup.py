# setup for durank package

import os.path
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

setup(
        name='durank',
        version='0.1',
        description='disk usage with ranking',
        author='Matthew Clapp',
        author_email='itsayellow+dev@gmail.com',
        license='MIT',
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3'
            ],
        keywords='du ranking usage',
        py_modules=['durank'],
        entry_points={
            'console_scripts':[
                'durank=durank:cli'
                ]
            },
        python_requires='>=3',
        )

