#!/usr/bin/env python
"""
Runs pictures through image specific external optimizers
"""
from __future__ import print_function
from __future__ import division

import os
import argparse
import multiprocessing
import dateutil.parser
import time

import extern
import stats
import timestamp
import optimize
import file_format
import png
import jpeg
import gif
import comic
import name

__version__ = '1.2.0'

# Programs
PROGRAMS = set(png.PROGRAMS + gif.PROGRAMS + jpeg.PROGRAMS)


def get_arguments():
    """parses the command line"""
    usage = "%(prog)s [arguments] [image files]"
    programs_str = ', '.join(PROGRAMS)
    description = "Uses "+programs_str+" if they are on the path."
    parser = argparse.ArgumentParser(usage=usage, description=description)
    parser.add_argument("-r", "--recurse", action="store_true",
                        dest="recurse", default=0,
                        help="Recurse down through directories ignoring the"
                        "image file arguments on the command line")
    parser.add_argument("-v", "--verbose", action="count",
                        dest="verbose", default=0,
                        help="Display more output. -v (default) and -vv "
                        "(noisy)")
    parser.add_argument("-Q", "--quiet", action="store_const",
                        dest="verbose", const=-1,
                        help="Display little to no output")
    parser.add_argument("-a", "--enable_advpng", action="store_true",
                        dest="advpng", default=0,
                        help="Optimize with advpng (disabled by default)")
    parser.add_argument("-c", "--comics", action="store_true",
                        dest="comics", default=0,
                        help="Also optimize comic book archives (cbz & cbr)")
    parser.add_argument("-f", "--formats", action="store", dest="formats",
                        default=file_format.DEFAULT_FORMATS,
                        help="Only optimize images of the specifed '%s' "
                        "delimited formats from: %s" %
                        (file_format.FORMAT_DELIMETER,
                         ', '.join(sorted(file_format.ALL_FORMATS))))
    parser.add_argument("-O", "--disable_optipng", action="store_false",
                        dest="optipng", default=1,
                        help="Do not optimize with optipng")
    parser.add_argument("-P", "--disable_pngout", action="store_false",
                        dest="pngout", default=1,
                        help="Do not optimize with pngout")
    parser.add_argument("-J", "--disable_jpegrescan", action="store_false",
                        dest="jpegrescan", default=1,
                        help="Do not optimize with jpegrescan")
    parser.add_argument("-E", "--disable_progressive", action="store_false",
                        dest="jpegtran_prog", default=1,
                        help="Don't try to reduce size by making "
                        "progressive JPEGs with jpegtran")
    parser.add_argument("-Z", "--disable_mozjpeg", action="store_false",
                        dest="mozjpeg", default=1,
                        help="Do not optimize with mozjpeg")
    parser.add_argument("-T", "--disable_jpegtran", action="store_false",
                        dest="jpegtran", default=1,
                        help="Do not optimize with jpegtran")
    parser.add_argument("-G", "--disable_gifsicle", action="store_false",
                        dest="gifsicle", default=1,
                        help="disable optimizing animated GIFs")
    parser.add_argument("-Y", "--disable_convert_type", action="store_const",
                        dest="to_png_formats",
                        const=png.PNG_FORMATS,
                        default=png.PNG_CONVERTABLE_FORMATS,
                        help="Do not convert other lossless formats like "
                        " %s to PNG when optimizing. By default, %s"
                        " does convert these formats to PNG" %
                        (', '.join(png.LOSSLESS_FORMATS),
                         name.PROGRAM_NAME))
    parser.add_argument("-S", "--disable_follow_symlinks",
                        action="store_false",
                        dest="follow_symlinks", default=1,
                        help="disable following symlinks for files and "
                        "directories")
    parser.add_argument("-d", "--dir", action="store", dest="dir",
                        default=os.getcwd(),
                        help="Directory to change to before optimiziaton")
    parser.add_argument("-b", "--bigger", action="store_true",
                        dest="bigger", default=0,
                        help="Save optimized files that are larger than "
                        "the originals")
    parser.add_argument("-t", "--record_timestamp", action="store_true",
                        dest="record_timestamp", default=0,
                        help="Store the time of the optimization of full "
                        "directories in directory local dotfiles.")
    parser.add_argument("-D", "--optimize_after", action="store",
                        dest="optimize_after", default=None,
                        help="only optimize files after the specified "
                        "timestamp. Supercedes -t")
    parser.add_argument("-N", "--noop", action="store_true",
                        dest="test", default=0,
                        help="Do not replace files with optimized versions")
    parser.add_argument("-l", "--list", action="store_true",
                        dest="list_only", default=0,
                        help="Only list files that would be optimized")
    parser.add_argument("-V", "--version", action="version",
                        version=__version__,
                        help="display the version number")
    parser.add_argument("-M", "--destroy_metadata", action="store_true",
                        dest="destroy_metadata", default=0,
                        help="*Destroy* metadata like EXIF and JFIF")
    parser.add_argument("paths", metavar="path", type=str, nargs="+",
                        help="File or directory paths to optimize")
    parser.add_argument("-j", "--jobs", type=int, action="store",
                        dest="jobs", default=multiprocessing.cpu_count(),
                        help="Number of parallel jobs to run simultaneously.")

    return parser.parse_args()


def process_arguments(arguments):
    """ Recomputer special cases for input arguments """
    extern.program_reqs(arguments, PROGRAMS)

    arguments.verbose += 1
    arguments.paths = set(arguments.paths)
    arguments.archive_name = None

    if arguments.formats == file_format.DEFAULT_FORMATS:
        arguments.formats = arguments.to_png_formats | \
            jpeg.JPEG_FORMATS | gif.GIF_FORMATS
    else:
        arguments.formats = arguments.formats.upper().split(
            file_format.FORMAT_DELIMETER)

    if arguments.comics:
        arguments.formats = arguments.formats | comic.COMIC_FORMATS

    if arguments.optimize_after is not None:
        try:
            after_dt = dateutil.parser.parse(arguments.optimize_after)
            arguments.optimize_after = time.mktime(after_dt.timetuple())
        except Exception as ex:
            print(ex)
            print('Could not parse date to optimize after.')
            exit(1)

    if arguments.jobs < 1:
        arguments.jobs = 1

    # Make a rough guess about weather or not to invoke multithreding
    # jpegrescan '-t' uses three threads
    # one off multithread switch bcaseu this is the only one right now
    files_in_paths = 0
    non_file_in_paths = False
    for filename in arguments.paths:
        if os.path.isfile(filename):
            files_in_paths += 1
        else:
            non_file_in_paths = True
    arguments.jpegrescan_multithread = not non_file_in_paths and \
        arguments.jobs - (files_in_paths*3) > -1

    return arguments


def run_main(raw_arguments):
    """ The main optimization call """

    arguments = process_arguments(raw_arguments)

    # Setup Multiprocessing
    manager = multiprocessing.Manager()
    total_bytes_in = manager.Value(int, 0)
    total_bytes_out = manager.Value(int, 0)
    nag_about_gifs = manager.Value(bool, False)
    pool = multiprocessing.Pool(arguments.jobs)

    multiproc = {'pool': pool, 'in': total_bytes_in, 'out': total_bytes_out,
                 'nag_about_gifs': nag_about_gifs}

    # Optimize Files
    record_dirs = optimize.optimize_all_files(multiproc, arguments)

    # Shut down multiprocessing
    pool.close()
    pool.join()

    # Write timestamps
    for filename in record_dirs:
        timestamp.record_timestamp(filename, arguments)

    # Finish by reporting totals
    stats.report_totals(multiproc['in'].get(), multiproc['out'].get(),
                        arguments, multiproc['nag_about_gifs'].get())


def main():
    """main"""
    raw_arguments = get_arguments()
    run_main(raw_arguments)


if __name__ == '__main__':
    main()
