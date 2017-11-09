# Introduction

This code enables you to recursively index a folder structure containing music
files.  It reads the ID3 tags contained in the files and creates a hierarchical
index of Artist - Album - Track and stores this in a yaml file in your local
directory.  It is also albe to do this from the xml export from iTunes.

I have used this script to help me identify albums that I had bought as
downloads after I re-ripped my CD collection into flac; the downloaded albums
were missing from the flac archive so I copied across the mp3 downloads to
ensure I had a complete collection of music.

# Usage

## Indexing

Index a hierarchical folder structure from disk

~~~ shell
python3 albums.py index <path to my music files>
~~~

Create an index from an iTunes export.  In iTunes do:
File -> Library -> Export Library, which can create a `Library.xml` file

~~~ shell
python3 albums.py index <path to Library.xml>
~~~

## Comparing indices

Compare a reference index, with a test index.

~~~ shell
python3 albums.py compare reference_index.yml test_index.yml
~~~
