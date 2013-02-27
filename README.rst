letmehear
=========
http://github.com/idlesign/letmehear


What's that
-----------

*letmehear is a SoX based audio file merge-n-splitter appropriate to resplit audio books.*

It is able to function both as a Python module and in command line mode.


Features
--------

- Large variety of supported input audio formats (due to SoX).
- Batch audio files processing (including recursive path traversing).
- Adjustable output audio parts length.
- Adjustable output audio speed.
- Adjustable backshift length (number of seconds from the end of a previous audio part to place at the beginning of a next one).


Requirements
------------

letmehear depends upon SoX command line utility - http://sox.sourceforge.net.

Ubuntu users may install the following SoX packages: `sox`, `libsox-fmt-all`.


Usage
-----

1. `import letmehear` - if you want to use it as module. *LetMe* class is at your service.
2. `./letmehear.py -h` in command line - to get help on utility usage.

In the following example we merge all audio files into one, increase its playback speed
to 1.2, and resplit it into chunks of 3 minutes, putting them into `letmehear` directory
created inside `/home/idlesign/audiobook_1/`::

    ./letmehear.py -s 1.2 /home/idlesign/audiobook_1/


Dedication
----------

Dedicated to legacy Mystery car audio system of mine unable to digest one and a half hour mp3 file with another Discworld novel %)
