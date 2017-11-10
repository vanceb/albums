import os
import string
import logging
import argparse
import plistlib                 # To read iTunes export xml file
from tinytag import TinyTag     # ID3 Tag reader
import yaml


def parse_commandline():
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    parser = argparse.ArgumentParser(description='Compare albums from itunes'
                                     + 'against a file system')
    parser.add_argument('action',
                        help='The action you want to perform',
                        choices=['index', 'compare']
                        )
    parser.add_argument('files',
                        help='The file(s) to work on - compare needs exactly 2 files',
                        nargs='+'
                        )
    parser.add_argument('-l',
                        '--loglevel',
                        dest='loglevel',
                        action='store',
                        default='INFO',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
                        required=False,
                        help='The library xml file produced by iTunes->File->Library->Export Library'
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
    log = logging.getLogger(__name__)
    path = os.path.abspath(filename)
    log.info('Opening ' + path)
    data = plistlib.readPlist(path)

    tracks = data['Tracks']
    music = {}
    artist = ''
    album = ''
    track_name = ''
    for track_id in tracks:
        track = tracks[track_id]
        if 'Album Artist' in track:
            artist = track['Album Artist']
        elif 'Artist' in track:
            artist = track['Artist']
        else:
            artist=None
            log.warning("Unable to find Artist for track_id: " + track_id)

        if artist is not None:
            if 'Album' in track:
                album = track['Album']
            else:
                album = ''
                log.warning('Unable to get album for track_id: ' + track_id)

            if 'Name' in track:
                track_name = track['Name']
            else:
                track_name = ''
                log.warning('Unable to get track name for track_id: ' + track_id)

        if artist is not None:
            if artist not in music:
                music[artist] = {}
            if album not in music[artist]:
                music[artist][album] = [track_name]
            else:
                music[artist][album].append(track_name)
            log.debug('Processed: ' + artist + '/' + album + '/' + track_name)

    return music


def artist_album_from_dirs(basedir):
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

                if tag.title is None or tag.title == '':
                    log.warning('Unable to get track name for file: ' + path)
                    track_name = ''
                else:
                    track_name = tag.title

                if artist is not None:
                    if artist not in music:
                        music[artist] = {}
                    if album not in music[artist]:
                        music[artist][album] = [track_name]
                    else:
                        music[artist][album].append(track_name)
                    log.debug('Processed: ' + artist + '/' + album + '/' + track_name)

    return music


def index(location, save_yml=True, save_to=None):
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
        if save_yml:
            if save_to is not None:
                out = save_to
            else:
                name, ext = os.path.splitext(path)
                name = os.path.basename(name)
                if name is None or name == '':
                    name = 'index'
                out = name + '.yml'
            with open(out, 'w') as f:
                f.write(yaml.dump(music))
    return music


def tree_print(music):
    artists = 0
    albums = 0
    tracks = 0
    for artist in music:
        print(artist)
        artists += 1
        for album in music[artist]:
            print('\t' + album)
            albums += 1
            for track in music[artist][album]:
                print('\t\t' + track)
                tracks += 1

    print()
    print('Artists: ' + str(artists))
    print('Albums: ' + str(albums))
    print('Tracks: ' + str(tracks))


def aa_print(album_artist):
    for aa in album_artist:
        print(aa['artist'] + ' / ' + aa['album'])


def aa_save(album_artist, filename, separator=' :: '):
    with open(filename, 'w') as f:
        for aa in album_artist:
            f.write(aa['artist'] + separator + aa['album'] + '\n')


def normalise(txt):
    no_punctuation = str.maketrans("", "", string.punctuation)
    return txt.translate(no_punctuation).strip().lower()


def check(test, reference):
    log = logging.getLogger(__name__)
    log.debug('Started to check test against reference')
    # Create an index of the reference
    ref_artist = {}     # Hash lookup of normalised artists to full artist names
    ref_album = {}      # Hash lookup of normalised albums to full titles
    album_artist = {}   # Lookup from album to list of artists
    log.debug('Building reference indices')
    log.debug('Creating artist index')
    for artist in reference:
        # Normalise the artist name and fill ref_artist
        norm = normalise(artist)
        log.debug('Normalised ' + artist + ' to ' + norm)
        if norm in ref_artist:
            if ref_artist[norm] != artist:
                log.debug('Additional entry for ' + norm + ' created for ' + artist)
                ref_artist[norm].append(artist)
            else:
                log.debug('Artist ' + artist + ' already indexed, skipping')
        else:
            log.debug('New entry for ' + norm + ' created for ' + artist)
            ref_artist[norm] = [artist]

        # for each of the artists albums
        log.debug('Creating album index for ' + artist)
        for album in reference[artist]:
            # Normalise the album name and fill ref_album
            norm = normalise(album)
            log.debug('Normalised ' + album + ' to ' + norm)
            if norm in ref_album:
                found = False
                for albums in ref_album[norm]:
                    if albums == album:
                        found = True
                if not found:
                    log.debug('Additional entry for ' + norm + ' created for ' + album)
                    ref_album[norm].append(album)
                else:
                    log.debug('Duplicate album name ' + album + ', skipping')
            else:
                log.debug('New entry for ' + norm + ' created for ' + album)
                ref_album[norm] = [album]

            # Create a reverse lookup from album to list of artists
            log.debug('Creating reverse lookup of album to artist')
            if album in album_artist:
                log.debug('Additional entry for album ' + album + ' created for ' + artist)
                album_artist[album].append(artist)
            else:
                log.debug('New entry for ' + norm + ' created for ' + artist)
                album_artist[album] = [artist]

    # Create some structures to keep track of matches or possibles
    matched = []
    hit_artist = []
    hit_album = []
    miss = []

    # Loop over the test trying to look up against the reference
    log.debug('Begining matching')
    for artist in test:
        log.debug('Artist: ' + artist)
        # Look for the artist
        norm = normalise(artist)
        if norm in ref_artist:
            log.debug('Found match for ' + artist)
            found_artist = ref_artist[norm]
        else:
            log.debug('No match found for ' + artist)
            found_artist = None

        # Look for the album
        for album in test[artist]:
            log.debug('Album: ' + album)
            norm = normalise(album)
            if norm in ref_album:
                log.debug('Found match for ' + album)
                found_album = ref_album[norm]
            else:
                log.debug('No match found for ' + album)
                found_album = None

            # Make sense of the matches
            if found_artist is not None:
                # We matched a normalised artist
                if found_album is not None:
                    # We matched a normalised album
                    # Need to check that the album and artist correlate
                    # We may get back a list of artists or albums...
                    log.debug('Matched artist and album')
                    hit = 0
                    poss = []
                    for artist in found_artist:
                        for album in found_album:
                            try:
                                # This will throw an exception if no correlation
                                tracks = reference[artist][album]
                                # No exception so we have a hit
                                hit += 1
                                poss.append({'artist': artist, 'album': album})
                            except:
                                # Do nothing, but continue to loop over
                                # possibilities
                                pass
                    if hit == 0:
                        # No correlation between the matched artist and album!
                        log.info('No correlation: ' + artist + '/' + album)
                        miss.append({'artist': artist, 'album': album})
                    elif hit == 1:
                        # A single correlation - assume correct
                        log.info('Found a match: ' + artist + '/' + album)
                        matched.append({'artist': poss[0]['artist'],
                                       'album': poss[0]['album']})
                    else:
                        # Multiple possibilities
                        log.info('Multiple hits: ' + artist + '/' + album)
                        hit_album.append({'artist': artist, 'album': album})
                else:
                    # Hit the artist only
                    log.info('Artist only: ' + artist + '/' + album)
                    hit_artist.append({'artist': artist, 'album': album})
            else:
                # We didn't match a normalised artist
                if found_album is not None:
                    # We hit an album title
                    log.info('Album only: ' + artist + '/' + album)
                    hit_album.append({'artist': artist, 'album': album})
                else:
                    # Didn't hit anything
                    log.info('Miss: ' + artist + '/' + album)
                    miss.append({'artist': artist, 'album': album})

    return matched, miss, hit_artist, hit_album


def main():
    logging.basicConfig()
    log = logging.getLogger(__name__)
    args, parser = parse_commandline()

    if args.action == 'index':
        for f in args.files:
            index(f)
    elif args.action == 'compare':
        if len(args.files) != 2:
            parser.print_help()
            sys.exit(-1)
        else:
            reference = index(args.files[0])
            test = index(args.files[1])
            matched, miss, hit_artist, hit_album = check(test, reference)

            aa_save(matched, 'matched.txt')
            aa_save(miss, 'miss.txt')
            aa_save(hit_artist, 'hit_artist.txt')
            aa_save(hit_album, 'hit_album.txt')


if __name__ == "__main__":
    main()
