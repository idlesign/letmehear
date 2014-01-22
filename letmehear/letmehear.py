#!/usr/bin/env python
"""
letmehear is essentially a wrapper for mighty SoX utility - http://sox.sourceforge.net/.

SoX with appropriate plugins should be installed for letmehear to function.
Ubuntu users may install the following SoX packages: `sox`, `libsox-fmt-all`.


letmehear can function both as a Python module and in command line mode.
"""
import os
import re
import logging
import argparse

from collections import defaultdict
from subprocess import Popen, PIPE
from hashlib import md5

# Regexp to fetch audio formats list from `sox -h` output.
RE_SOX_AUDIO_SUPPORT = re.compile('AUDIO FILE FORMATS:(.*)\n', re.MULTILINE & re.IGNORECASE)


class LetMeError(Exception):
    """Exception type raised by letmehear."""


class LetMe(object):
    """letmehear functionality is encapsulated in this class.

    Usage example:
        letme = LetMe('/home/idle/ebooks_to_process/')
        letme.hear()

    This will search `/home/idle/ebooks_to_process/` and subdirectories
    for audio files, combine all previously splitted audios into one
    (if more than one file is found in the directory), and chop it into
    files with given length (if not set by the `set_part_length` method,
    default length for 180 seconds is used, i.e. 3 minutes).
    All parts will be stored in `letmehear` named directory under each
    of source directories.

    """

    # The name of a temporary source audio file, which is used to make parts from.
    # We used flac instead of wav both to save space and prevent errors that may occur
    # in wav if file is too big.
    _source_filename = '_letmehear.tmp.flac'
    # Part length in seconds.
    _part_length = 180
    # Backshift in seconds.
    _backshift = 1
    # Some lengthy shell command won't be executed on dry run.
    _dry_run = False
    # Speed ratio.
    _speed = None

    def __init__(self, source_path, dest_path=None, use_logging=logging.INFO):
        """Prepares letmehear to for audio processing.

        `source_path` - Absolute or relative to the current directory path,
                        containing audio file(s) or subdirectories with
                        audio file(s) to process.

        `dest_path` - Absolute or relative to the current directory path
                      to store output files in.
                      If None, output files are saved in `letmehear` directory
                      in the same directory as input file(s).

        `use_logging` - Defines the verbosity level of letmehear. All messages
                        produced by the application are logged with `logging` module.
                        Examples: logging.INFO, logging.DEBUG.

        """
        self.path_source = os.path.abspath(source_path)
        self.path_target = dest_path

        if use_logging:
            self._configure_logging(use_logging)

        logging.info('Source path: %s' % self.path_source)
        if not os.path.exists(self.path_source):
            raise LetMeError('Path "%s" is not found.' % self.path_source)

        if dest_path is not None:
            self.path_target = os.path.abspath(dest_path)
            os.chdir(self.path_source)

    def _process_command(self, command, stdout=None, supress_dry_run=False):
        """Executes shell command with subprocess.Popen.
        Returns tuple, where first element is a process return code,
        and the second is a tuple of stdout and stderr output.
        """
        logging.debug('Executing shell command: %s' % command)
        if (self._dry_run and supress_dry_run) or not self._dry_run:
            prc = Popen(command, shell=True, stdout=stdout)
            std = list(prc.communicate())
            if std[0] is not None:
                std[0] = std[0].decode('utf-8')
            return prc.returncode, std
        return 0, ('', '')

    @staticmethod
    def _configure_logging(verbosity_lvl=logging.INFO):
        """Switches on logging at given level."""
        logging.basicConfig(level=verbosity_lvl, format='%(levelname)s: %(message)s')

    def _create_target_path(self, path):
        """Creates a directory for target files."""
        if not os.path.exists(path) and not self._dry_run:
            logging.debug('Creating target path: %s ...' % path)
            try:
                os.makedirs(path)
            except OSError:
                raise LetMeError('Unable to create target path: %s' % path)

    def set_dry_run(self):
        """Sets letmehear into dry run mode, when all requested actions
        are only simulated, and no changes are written to filesystem.

        """
        self._dry_run = True

    def get_dir_files(self, recursive=False):
        """Creates and returns dictionary of files in source directory.
        `recursive` - if True search is also performed within subdirectories.

        """
        logging.info('Enumerating files under the source path (recursive=%s) ...' % recursive)
        files = {}
        if not recursive:
            files[self.path_source] = [file for file in os.listdir(self.path_source) if os.path.isfile(os.path.join(self.path_source, file))]
        else:
            for current_dir, sub_dirs, dir_files in os.walk(self.path_source):
                files[os.path.join(self.path_source, current_dir)] = [file for file in dir_files]

        return files

    def filter_target_extensions(self, files_dict):
        """Takes file dictionary created with `get_dir_files` and returns
        dictionary of the same kind containing only audio files of supported
        types.

        """
        files_filtered = defaultdict(list)
        supported_formats = self.sox_get_supported_formats()
        logging.info('Filtering audio files ...')
        paths = list(files_dict.keys())

        for path in paths:
            if not path.endswith('letmehear'):
                files = sorted(files_dict[path])
                for file in files:
                    if os.path.splitext(file)[1].lstrip('.').lower() in supported_formats:
                        files_filtered[path].append(file)
        return files_filtered

    def set_part_length(self, seconds):
        """Used to set output file(s) length in seconds."""
        self._part_length = seconds

    def set_backshift(self, seconds):
        """Used to set a backshift - number of seconds for every
        part to be taken from a previous one.

        """
        self._backshift = seconds

    def set_speed(self, ratio):
        """Used to set output file(s) speed. Expects ratio modifier, e.g. 1.3 """
        self._speed = ratio

    def sox_check_is_available(self):
        """Checks whether SoX is available."""
        result = self._process_command('sox -h', PIPE, supress_dry_run=True)
        return result[0] == 0

    def sox_get_supported_formats(self):
        """Asks SoX for supported audio files formats and returns them as a list."""
        formats = ['wav']
        result = self._process_command('sox -h', PIPE, supress_dry_run=True)
        matches = re.findall(RE_SOX_AUDIO_SUPPORT, result[1][0])

        if matches is not None:
            formats = matches[0].strip().split(' ')

        logging.debug('Sox supported audio formats: %s' % formats)
        return formats

    def sox_get_sample_rates(self, files):
        """Calculates maximum and minimum sample rates for given files.
        Returns tuple (min_rate, max_rate, files_to_rates_dict).

        """
        min_rate = max_rate = None
        files_to_rates_dict = {}

        for file in files:
            result = self._process_command('soxi -r "%s"' % file, PIPE)
            try:
                rate = int(result[1][0].strip('\n'))
            except ValueError:
                raise LetMeError('Unable to read sample rate from %s' % file)

            files_to_rates_dict[file] = rate

            logging.debug('\nSample rate `%s` for `%s`' % (rate, file))

            if max_rate is None or rate > max_rate:
                max_rate = rate

            if min_rate is None or rate < min_rate:
                min_rate = rate

        logging.debug('Sample rates: min - %s, max - %s' % (min_rate, max_rate))
        return min_rate, max_rate, files_to_rates_dict

    @staticmethod
    def get_resampled_filename(filepath):
        """Returns temporary resampled file name from filepath."""
        try:
            filepath = filepath.encode('utf-8')
        except UnicodeDecodeError:
            pass
        return 'tmp_%s.flac' % md5(filepath).hexdigest()

    def sox_resample(self, file, target_rate, target_dir):
        target_file = os.path.join(target_dir, self.get_resampled_filename(file))
        logging.info('MUST resample "%s" to create source file. Resampling to %s ...\n      Target: %s' %
                     (file, target_rate, target_file))
        command = 'sox -S "%(input)s" -r %(rate)s "%(target)s"' % {'input': file, 'rate': target_rate, 'target': target_file}
        self._process_command(command)

    def sox_create_source_file(self, files, target):
        """Creates a source file at given target path from one
        more input files.

        """
        logging.debug('Source file will be made from:\n%s\n' % '\n'.join(files))
        logging.info('Making source file: %s' % target)

        options = ''
        effects = ''

        files_to_precess = []
        if len(files) > 1:
            options = '--combine concatenate'

        target_dir = os.path.dirname(target)
        for file in files:
            resampled_file = os.path.join(target_dir, self.get_resampled_filename(file))
            if os.path.exists(resampled_file):
                file = resampled_file
            files_to_precess.append(file)

        if self._speed is not None:
            effects = 'speed %s' % self._speed

        command = 'sox -S --ignore-length %(options)s "%(files)s" "%(target)s" %(effects)s' % {
            'options': options, 'files': '" "'.join(files_to_precess), 'target': target, 'effects': effects}

        self._process_command(command)

    def sox_get_audio_length(self, audio_file):
        """Asks SoX for given file length in seconds and returns them as float.
        Returns 1000 on dry run.

        """
        logging.info('Getting source file length ...')
        result = self._process_command('soxi -D "%s"' % audio_file, PIPE)
        if result[1][0] != '':
            return float(result[1][0].strip('\n'))
        else:
            return 1000

    def sox_chop_source_audio(self, source_filename, part_length, backshift=0):
        """Using SoX chops source audio file into parts of given length.
        Chopping is done in such a way that every next audio part contains
        one (1) second from the previous.

        """
        logging.info('Preparing for source file chopping ...')

        wav_length = self.sox_get_audio_length(source_filename)
        if wav_length <= part_length:
            parts_count = 1
        else:
            # Calculate audio length with one second back shift. Also known as possum formula %)
            parts_count = int(round(wav_length / float(part_length - backshift), 0))
        parts_count_len = len(str(parts_count))

        logging.info('Chopping information:\n' \
                     '      Source file length: %(source)s second(s)\n' \
                     '      Requested part length: %(part)s second(s)\n' \
                     '      Backshift: %(back)s second(s)\n' \
                     '      Parts count: %(parts_cnt)s' %
             {'source': wav_length, 'part': part_length, 'parts_cnt': parts_count, 'back': backshift})

        logging.info('Starting chopping ...')
        for index in range(0, parts_count):
            start_pos = index * part_length
            if start_pos > 0:
                # We need to shift all but the first part for `backshift` seconds backward
                # to not to loose some phrases on chopping.
                start_pos -= (index * backshift)
            part_number = str(index + 1).rjust(parts_count_len, '0')

            # This will strip ID3Tags from file - they are identical thus uninformative.
            comment = '--comment ""'

            target = part_number
            logging.info('Working on %s.mp3 [%s/%s - %s%%] ...' % (target, int(part_number), parts_count, int(int(part_number) * 100 / parts_count)))
            command = 'sox -V1 "%(source)s" %(comment)s %(target)s.mp3 trim %(start_pos)s %(length)s' % {
                'source': source_filename, 'target': target, 'start_pos': start_pos, 'length': part_length, 'comment': comment}
            self._process_command(command, PIPE)
        logging.info('Chopped.\n')

    @staticmethod
    def remove_tmp_sources(source_filename):
        """Removes temporary created source files."""
        logging.info('Removing temporary files ...')
        source_dir = os.path.dirname(source_filename)
        if os.path.exists(source_filename):
            os.remove(source_filename)
        for file in os.listdir(source_dir):
            if file.startswith('tmp_'):
                os.remove(os.path.join(source_dir, file))

    def process_source_file(self, path, files, source_filename):
        """Initiates source file processing."""
        os.chdir(path)

        min_rate, max_rate, files_to_rates_dict = self.sox_get_sample_rates(files)
        if min_rate != max_rate:
            for file in files:
                if files_to_rates_dict[file] != max_rate:
                    self.sox_resample(file, max_rate, os.path.dirname(source_filename))

        self.sox_create_source_file(files, source_filename)
        os.chdir(os.path.dirname(source_filename))
        self.sox_chop_source_audio(source_filename, self._part_length, self._backshift)
        self.remove_tmp_sources(source_filename)

    def hear(self, recursive=False):
        """God method that lets, as a consequence, you hear your precious
        audio book with your mad-as-a-hatter legacy audio player not able
        to play files of one hour plus length.

        Staying cool, staying cool. Do not worry, be happy at last.
        """
        if self.path_target is not None and not os.path.exists(self.path_target):
            self._create_target_path(self.path_target)

        files_dict = self.filter_target_extensions(self.get_dir_files(recursive))

        paths = sorted(files_dict.keys())
        for path in paths:
            logging.info('%s\n      Working on: %s\n' % ('====' * 10, path))

            if self.path_target is None:
                # When a target path is not specified, create `letmehear` subdirectory
                # in every directory we are working at.
                target_path = os.path.join(path, 'letmehear')
            else:
                # When a target path is specified, we create a subdirectory there
                # named after the directory we are working on.
                target_path = os.path.join(self.path_target, os.path.split(path)[1])

            self._create_target_path(target_path)
            logging.info('Target (output) path: %s' % target_path)

            source_filename = os.path.join(target_path, self._source_filename)
            self.process_source_file(path, files_dict[path], source_filename)

        logging.info('We are done now. Thank you.\n')


def main():

    argparser = argparse.ArgumentParser('letmehear.py')

    argparser.add_argument('source_path', help='Absolute or relative (to the current) source path of input audio file(s).')
    argparser.add_argument('-r', help='Recursion flag to search directories under the source_path.', action='store_true')
    argparser.add_argument('-d', help='Absolute or relative (to the current) destination path for output audio file(s).')
    argparser.add_argument('-l', help='Length (in seconds) for each output audio file.', type=int)
    argparser.add_argument('-b', help='Backshift - number of seconds for every part to be taken from a previous one.', type=int)
    argparser.add_argument('-s', help='Speed ratio.', type=float)
    argparser.add_argument('--dry', help='Perform the dry run with no changes done to filesystem.', action='store_true')
    argparser.add_argument('--debug', help='Show debug messages while processing.', action='store_true')

    parsed = argparser.parse_args()
    kwargs = {'source_path': parsed.source_path}

    if parsed.d is not None:
        kwargs['dest_path'] = parsed.d

    if parsed.debug:
        kwargs['use_logging'] = logging.DEBUG

    try:
        letme = LetMe(**kwargs)

        if not letme.sox_check_is_available():
            raise LetMeError('SoX seems not available. Please install it (e.g. `sudo apt-get install sox libsox-fmt-all`).')

        if parsed.l is not None:
            letme.set_part_length(parsed.l)

        if parsed.b is not None:
            letme.set_backshift(parsed.b)

        if parsed.s is not None:
            letme.set_speed(parsed.s)

        if parsed.dry:
            letme.set_dry_run()

        letme.hear(parsed.r)
    except LetMeError as e:
        logging.error('ERROR: %s' % e)


if __name__ == '__main__':
    main()
