"""Provide basic m3u playlist writing."""

import os.path
import logging


class Playlist:
    """Class encapsulating an m3u playlist."""

    def __init__(self, filename=None):
        """Initialise the class and methods."""
        self._filename = filename
        self._songs = []

    def __str__(self):
        """Provide a string version of self."""
        return "Playlist(" + self._filename + ")"

    @property
    def filename(self):
        """Get the filename of the playlist."""
        return self._filename

    @filename.setter
    def filename(self, filename):
        """Set the filename of the playlist."""
        self._filename = os.path.abspath(filename)

    def append(self, tag_data):
        """
        Add a song to the playlist.

        Args:
            tag_data: must be a dictionary-like object containing at least
            the following keys:  title, location, duration

        Returns:
            self
        """
        if 'title' in tag_data \
           and 'location' in tag_data \
           and 'duration' in tag_data:
            self._songs.append(tag_data)
        else:
            raise ValueError
        return self

    def insert(self, position, tag_data):
        """
        Insert a song into the playlist.

        Args:
            position: Thje location at which to insert the song
            tag_data: Same restrictions as for append

        Returns:
            self
        """
        log = logging.getLogger(__name__)
        if 'title' in tag_data \
           and 'location' in tag_data \
           and 'duration' in tag_data:
            self._songs.insert(position, tag_data)
        else:
            log.warning("Song not added to playlist: " + str(tag_data))
            raise ValueError

    def remove(self, tag_data):
        """Remove item from the playlist."""
        self._songs.remove(tag_data)

    def write(self, relative=True, record_markers=True):
        """
        Write the playlist to disk.

        Args:
            relative: Should we use relative paths?
            record_markers: Should we use the #EXT... markers?

        Throws:
            IOError if problems writing the file
        """
        if self._filename is None:
            raise IOError

        with open(self._filename, 'w') as f:
            if record_markers:
                f.write('#EXTM3U\n')
            for song in self._songs:
                if record_markers:
                    record_marker = ('#EXTINF:'
                                     + str(int(song['duration'])) +
                                     "," + song['title'] + '\n'
                                     )
                    f.write(record_marker)

                if relative:
                    basedir = os.path.dirname(self._filename)
                    location = os.path.relpath(song['location'], start=basedir)
                else:
                    location = song['location']
                location += '\n'
                f.write(location)
