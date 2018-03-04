"""
Indexes and compares music files.

This code enables the parsing of music files, creating a hierarchical index
of artist -> album -> track.  It also allows for the comparison of
2 hierarchical indices creating files of albums that are common as well as
  albums that appear only in each of the indexes.
"""

import os
import sys
import string
import logging
import argparse
import plistlib                 # To read iTunes export xml file
from tinytag import TinyTag     # ID3 Tag reader
import yaml


def parse_commandline():
    """
    Parse the command line.

    This function parses the command line options for running the script as
    a main program
    """
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    parser = argparse.ArgumentParser(description="""
    Compare albums from multiple sources to help identify differences.  The
    sources can be iTunes export xml file, or a directory hierarchy containing
    music files.  For iTunes export the metadata is extracted from the xml file
    itself whereas for a directory of music the data is collected from the ID3
    tags contained in the music file.

    Minimal normalization is performed before comparison to negate the effect
    of punctuation, but otherwise the comparison is looking for an exact match.

    To allow for multiple comparisons maybe against a static source you can
    index the source into a yaml file.
    """)
    parser.add_argument('action',
                        help="""
    The action you wish to perform.  index creates an xml file froom the
    source, whereas compare compares exactly two sources.
    """,
                        choices=['index', 'compare']
                        )
    parser.add_argument('files',
                        help='The file(s) to work on - compare needs exactly '
                             + '2 files',
                        nargs='+'
                        )
    parser.add_argument('-l',
                        '--loglevel',
                        dest='loglevel',
                        action='store',
                        default='INFO',
                        choices=['CRITICAL',
                                 'ERROR',
                                 'WARNING',
                                 'INFO',
                                 'DEBUG'],
                        required=False,
                        help='Level of logging required'
                        )
    args = parser.parse_args()
    if args.loglevel.upper() == 'CRITICAL':
        log.setLevel(logging.CRITICAL)
    elif args.loglevel.upper() == 'ERROR  ':
        log.setLevel(logging.ERROR)
    elif args.loglevel.upper() == 'WARNING':
        log.setLevel(logging.WARNING)
    elif args.loglevel.upper() == 'INFO':
        log.setLevel(logging.INFO)
    elif args.loglevel.upper() == 'DEBUG':
        log.setLevel(logging.DEBUG)
    else:
        log.error('Unexpected log level!')

    log.debug('Commandline arguments: ' + str(args))
    return args, parser


def artist_album_from_xml(filename):
    """
    Index music metadata from iTunes plist xml files.

    This function indexes the contents of an iTunes exported library.  The
    exported library is in plist xml format.

    Args:
        filename:  The path to the xml file containing the export

    Returns:
        The function returns a hierarchical dictionary, where the first level
        keys are the 'Artist'm the second level keys are the 'Album'.  The
        third level is a list containing the track names in order of discovery

        e.g.

        music = artiust_album_from_xml('Library.xml')
        track_list = music['AC/DC']['Back in Black']  # Python list of tracks

    """
    log = logging.getLogger(__name__)
    path = os.path.abspath(filename)
    log.info('Opening ' + path)
    data = plistlib.readPlist(path)

    tracks = data['Tracks']
    music = {}
    artist = ''
    album = ''
    for track_id in tracks:
        track_tags = {}
        track = tracks[track_id]
        if 'Album Artist' in track:
            artist = track['Album Artist']
        elif 'Artist' in track:
            artist = track['Artist']
        else:
            artist = None
            log.warning("Unable to find Artist for track_id: " + track_id)

        if artist is not None:
            if 'Album' in track:
                album = track['Album']
            else:
                album = ''
                log.warning('Unable to get album for track_id: ' + track_id)

        if 'Album' in track:
            track_tags['album'] = track['Album']
        else:
            track_tags['album'] = None
        if 'Album Artist' in track:
            track_tags['album_artist'] = track['Album Artist']
        else:
            track_tags['album_artist'] = None
        if 'Artist' in track:
            track_tags['artist'] = track['Artist']
        else:
            track_tags['artist'] = None
        if 'Bit Rate' in track:
            track_tags['bitrate'] = track['Bit Rate']
        else:
            track_tags['bitrate'] = None
        if 'Disc Number' in track:
            track_tags['disc'] = track['Disc Number']
        else:
            track_tags['disc'] = None
        if 'Disc Count' in track:
            track_tags['disc_total'] = track['Disc Count']
        else:
            track_tags['disc_total'] = None
        if 'Total Time' in track:
            track_tags['duration'] = track['Total Time'] / 1000
        else:
            track_tags['duration'] = None
        if 'Size' in track:
            track_tags['filesize'] = track['Size']
        else:
            track_tags['filesize'] = None
        if 'Genre' in track:
            track_tags['genre'] = track['Genre']
        else:
            track_tags['genre'] = None
        if 'Sample Rate' in track:
            track_tags['samplerate'] = track['Sample Rate']
        else:
            track_tags['samplerate'] = None
        if 'Name' in track:
            track_tags['title'] = track['Name']
        else:
            track_tags['title'] = None
        if 'Track Number' in track:
            track_tags['track'] = track['Track Number']
        else:
            track_tags['track'] = None
        if 'Track Count' in track:
            track_tags['track_total'] = track['Track Count']
        else:
            track_tags['track_total'] = None
        if 'Release Date' in track:
            track_tags['release_date'] = track['Release Date']
        else:
            track_tags['release_date'] = None

        if artist is not None:
            if artist not in music:
                music[artist] = {}
            if album not in music[artist]:
                music[artist][album] = [track_tags]
            else:
                music[artist][album].append(track_tags)
            log.debug('Processed: ' + artist + '/' + album + '/'
                      + track_tags['title'])

    return music


def artist_album_from_dirs(basedir):
    """
    Recursively index music metadata from directory tree.

    Walk down a folder hierarchy starting at `basedir`.  When music files are
    found ID3 tags are read to get the artist, album, and track information,
    which is then placed into a hierarchical index.

    Args:
        basedir: The base directory from which to recursively descend.

    Returns:
        The function returns a hierarchical dictionary, where the first level
        keys are the 'Artist'm the second level keys are the 'Album'.  The
        third level is a list containing the track names in order of discovery

        e.g.

        music = artiust_album_from_dirs('/home/music')
        track_list = music['AC/DC']['Back in Black']  # Python list of tracks

    """
    log = logging.getLogger(__name__)
    music_file_exts = ['.mp3', '.flac', '.ogg', '.wav', '.wma', '.mp4', '.m4a']
    music = {}
    artist = None
    album = ''
    track_name = ''
    for dirName, subdirList, fileList in os.walk(basedir):
        for fname in fileList:
            path = os.path.abspath(dirName + '/' + fname)
            name, ext = os.path.splitext(path)
            if ext in music_file_exts:
                tag = TinyTag.get(path)

                if tag.albumartist is None or tag.albumartist == '':
                    if tag.artist is None or tag.artist == '':
                        log.warning('Unable to find artist for file: ' + path)
                        artist = None
                    else:
                        artist = tag.artist
                else:
                    artist = tag.albumartist

                if tag.album is None or tag.album == '':
                    log.warning('Unable to get album for file: ' + path)
                    album = ''
                else:
                    album = tag.album

                track_tags = {
                    'album': tag.album,
                    'album_artist': tag.albumartist,
                    'artist': tag.artist,
                    'bitrate': tag.bitrate,
                    'disc': tag.disc,
                    'disc_total': tag.disc_total,
                    'duration': tag.duration,
                    'filesize': tag.filesize,
                    'genre': tag.genre,
                    'samplerate': tag.samplerate,
                    'title': tag.title,
                    'track': tag.track,
                    'track_total': tag.track_total,
                    'release_date': tag.year
                    }

                if artist is not None:
                    if artist not in music:
                        music[artist] = {}
                    if album not in music[artist]:
                        music[artist][album] = [track_tags]
                    else:
                        music[artist][album].append(track_tags)
                    log.debug('Processed: ' + artist + '/' + album
                              + '/' + track_name)

    return music


def index(location, save_yml=True, save_to=None):
    """
    Wrapper function for index functions.

    Depending on whether the `location` is a file or directory it calls:

    album_artist_from_xml(location)  # If location is a file
    album_artist_from_dirs(location)  # If location is a directory

    Args:
        location:  A string containing the location of file or directory to be
                   indexed.
        save_yml:  Save the created index to a yaml file?  Defaults to True
        save_to:   The file name to save the yaml data to.  If None then
                   defaults to the local directory with a name the same as the
                   index location, but with a '.yml' extension
    Returns:
        A tuple of:
            hierarchical index of artist->album->track
            basefilename of the source
    """
    log = logging.getLogger(__name__)
    music = {}
    if location is not None:
        path = os.path.abspath(location)
        if os.path.isfile(path):
            name, ext = os.path.splitext(path)
            if ext == '.xml' or ext == '.plist':
                log.info('Indexing data from plist xml ' + path)
                music = artist_album_from_xml(path)
            elif ext == '.yml':
                save_yml = False
                log.info('Loading pre-indexed data from yml: ' + path)
                with open(path, 'r') as f:
                    music = yaml.load(f)
            else:
                log.error('Unrecognised file type: ' + path)

        elif os.path.isdir(path):
            log.info('Indexing data recursively from ' + path)
            music = artist_album_from_dirs(path)

        name, ext = os.path.splitext(path)
        name = os.path.basename(name)
        if name is None or name == '':
            name = 'index'

        if save_yml:
            if save_to is not None:
                out = save_to
            else:
                out = name + '.yml'
            with open(out, 'w') as f:
                f.write(yaml.dump(music))
    return music, name


def tree_print(music):
    """
    Print out hierarchical index data.

    Useful for debugging.  View the hierarchical index scructure created using
    the index() function.

    e.g.

    AC/DC
        Back in Black
            Hells Bells
            Shoot to Thrill
            ...

    Args:
        music:  A hierarchical datastructure to be printed out
    """
    artists = 0
    albums = 0
    tracks = 0
    for artist in music:
        print(artist)
        artists += 1
        for album in music[artist]:
            print('\t' + album)
            albums += 1
            for tag in music[artist][album]:
                print('\t\t' + tag.track)
                tracks += 1

    print()
    print('Artists: ' + str(artists))
    print('Albums: ' + str(albums))
    print('Tracks: ' + str(tracks))


def aa_print(album_artist, separator=' :: '):
    """
    Print out Artist album information.

    Print out artist and album from the datastructure returned from the compare
    function, which is a list of dictionaries containing 'artist' and 'album'
    keys.

    Useful for debugging certain datascructures or log files

    Args:
        album_artist:  A list of dictionaries containing at least
        'artist' and 'album' keys.
        separator:  The separator to use between the artist and album
    """
    for aa in album_artist:
        print(aa['artist'] + separator + aa['album'])


def aa_save(album_artist, filename, separator=' :: '):
    """
    Save artist album information.

    Saves artist album information to a file, one album per line

    Args:
        album_artist:  A list of dictionaries containing albums and associated
                       artist.
        filename:  The filename of the file to save the data to.
        separator:  The separator to use between the artist and the album.
    """
    with open(filename, 'w') as f:
        for aa in album_artist:
            f.write(aa['artist'] + separator + aa['album'] + '\n')


def normalise(txt):
    """
    Normalise text to allow for easier matching.

    Removes punctuation, strips whitespace from the ends of the text then
    lower-cases it.

    Args:
        txt:  The text to normalise

    Returns:
        A normalised string
    """
    no_punctuation = str.maketrans("", "", string.punctuation)
    return txt.translate(no_punctuation).strip().lower()


def normalise_index(index):
    """
    Normalise an index.

    Normalise an index to allow for better matching

    Args:
        index:  The index to normalise

    Returns:
        returns a normalised version of the index
    """
    log = logging.getLogger(__name__)
    norm = {}
    for artist in index:
        norm_artist = normalise(artist)
        log.debug('Norm Artist: ' + artist + '->' + norm_artist)
        norm[norm_artist] = {}
        for album in index[artist]:
            norm_album = normalise(album)
            log.debug('Norm Album: ' + album + '->' + norm_album)
            norm[norm_artist][norm_album] = []
            for tag in index[artist][album]:
                norm[norm_artist][norm_album] = tag

    return norm


def comp(a, b):
    """
    Compare albums in index a against those in index b.

    Compare hierarchical index a with hierarchical index b to create 2 lists:
    Comparison is to the album level only.  No track comparison is attempted.
        - both:  Album is in both indices
        - a_only:  Album is only in index a

    Args:
        a:  A hierarchical index of album->artist->tracks
        b:  A hierarchical index of album->artist->tracks

    Returns:
        returns a tuple of 2 artist-album lists:
            - both:  Album is in both indices
            - a_only:  Album is only in index a
    """
    log = logging.getLogger(__name__)
    norm_b = normalise_index(b)
    both = []
    a_only = []
    for artist in a:
        norm_artist = normalise(artist)
        for album in a[artist]:
            norm_album = normalise(album)
            match = False
            if norm_artist in norm_b:
                if norm_album in norm_b[norm_artist]:
                    match = True
            if match:
                log.debug('Hit: ' + artist + ' / ' + album)
                both.append({'artist': artist, 'album': album})
            else:
                log.debug('Miss: ' + artist + ' / ' + album)
                a_only.append({'artist': artist, 'album': album})
    return both, a_only


def compare(a, b):
    """
    Compare index a with index b in both directions.

    The comparison is only to the album level.  No track comparison is
    attempted.

    Compare hierarchical index a with hierarchical index b to create 3 lists:
        - both:  Album is in both indices
        - a_only:  Album is only in index a
        - b_only:  Album is only in index b

    Args:
        a:  A hierarchical index of album->artist->tracks
        b:  A hierarchical index of album->artist->tracks

    Returns:
        returns a tuple of 3 artist-album lists:
            - both:  Album is in both indices
            - a_only:  Album is only in index a
            - b_only:  Album is only in index b
    """
    both, a_only = comp(a, b)
    both, b_only = comp(b, a)
    return both, a_only, b_only


def main():
    """Run indexing and comparison operations from the command line."""
    logging.basicConfig()
    log = logging.getLogger(__name__)
    args, parser = parse_commandline()
    log.debug("Starting with: " + str(args))

    if args.action == 'index':
        for f in args.files:
            index(f)
    elif args.action == 'compare':
        if len(args.files) != 2:
            parser.print_help()
            sys.exit(-1)
        else:
            a, a_name = index(args.files[0])
            b, b_name = index(args.files[1])
            both, a_only, b_only = compare(a, b)

            aa_save(both, 'both.txt')
            aa_save(a_only, a_name + '_only.txt')
            aa_save(b_only, b_name + '_only.txt')


if __name__ == "__main__":
    main()
