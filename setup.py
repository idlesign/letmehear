import os
from setuptools import setup
from letmehear import VERSION


f = open(os.path.join(os.path.dirname(__file__), 'README.rst'))
README = f.read()
f.close()


setup(
    name='letmehear',
    version='.'.join(map(str, VERSION)),
    url='http://github.com/idlesign/letmehear',

    description='SoX based audio file merge-n-splitter appropriate to resplit audio books.',
    long_description=README,
    license='BSD 3-Clause License',

    author="Igor 'idle sign' Starikov",
    author_email='idlesign@yandex.ru',

    packages=['letmehear'],
    include_package_data=True,
    zip_safe=False,

    scripts=['bin/letmehear'],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Topic :: Multimedia :: Sound/Audio :: Conversion',
    ],
)
