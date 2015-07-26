"""
Optimize comic archives
"""
from __future__ import print_function
from __future__ import division

import copy
import os
import rarfile
import shutil
import traceback
import zipfile

import extern
import optimize
import stats


# Extensions
ARCHIVE_TMP_DIR_PREFIX = PROGRAM_NAME+'_tmp_'
ARCHIVE_TMP_DIR_TEMPLATE = ARCHIVE_TMP_DIR_PREFIX+'%s'
NEW_ARCHIVE_SUFFIX = '%s-optimized.cbz' % PROGRAM_NAME

CBR_EXT = '.cbr'
CBZ_EXT = '.cbz'
COMIC_EXTS = set((CBR_EXT, CBZ_EXT))

CBZ_FORMAT = 'CBZ'
CBR_FORMAT = 'CBR'
COMIC_FORMATS = set((CBZ_FORMAT, CBR_FORMAT))


def get_archive_tmp_dir(filename):
    """ get the name of the working dir to use for this filename"""
    head, tail = os.path.split(filename)
    return os.path.join(head, ARCHIVE_TMP_DIR_TEMPLATE % tail)


def comic_archive_write_zipfile(arguments, new_filename, tmp_dir):
    """ Zip up the files in the tempdir into the new filename """
    if arguments.verbose:
        print('Rezipping archive', end='')
    with zipfile.ZipFile(new_filename, 'w',
                         compression=zipfile.ZIP_DEFLATED) as new_zf:
        root_len = len(os.path.abspath(tmp_dir))
        for root, dirs, files in os.walk(tmp_dir):
            archive_root = os.path.abspath(root)[root_len:]
            for fname in files:
                fullpath = os.path.join(root, fname)
                archive_name = os.path.join(archive_root, fname)
                if arguments.verbose:
                    print('.', end='')
                new_zf.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)


def comic_archive_compress(args):
    """called back by every optimization inside a comic archive.
       when they're all done it creates the new archive and cleans up.
    """

    try:
        filename, total_bytes_in, total_bytes_out, arguments = args
        tmp_dir = get_archive_tmp_dir(filename)
        # archive into new filename
        new_filename = extern.replace_ext(filename, NEW_ARCHIVE_SUFFIX)

        comic_archive_write_zipfile(arguments, new_filename, tmp_dir)

        # Cleanup tmpdir
        if os.path.isdir(tmp_dir):
            if arguments.verbose:
                print('.', end='')
            shutil.rmtree(tmp_dir)
        if arguments.verbose:
            print('done.')

        report_stats = extern.cleanup_after_optimize(filename, new_filename,
                                                     arguments)
        stats.optimize_accounting(report_stats, total_bytes_in,
                                  total_bytes_out, arguments)
    except Exception as exc:
        print(exc)
        traceback.print_exc(exc)
        raise exc


def comic_archive_uncompress(filename, image_format, arguments):
    """ uncompress comic archives and return the name of the working
        directory we uncompressed into """

    if not arguments.comics:
        report = ['Skipping archive file: %s' % filename]
        report_list = [report]
        bytes_diff = {'in': 0, 'out': 0}
        return (bytes_diff, report_list)

    if arguments.verbose:
        truncated_filename = stats.truncate_cwd(filename, arguments)
        print("Extracting %s..." % truncated_filename, end='')

    # create the tmpdir
    tmp_dir = get_archive_tmp_dir(filename)
    if os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir)
    os.mkdir(tmp_dir)

    # extract archvie into the tmpdir
    if image_format == CBZ_FORMAT:
        with zipfile.ZipFile(filename, 'r') as zfile:
            zfile.extractall(tmp_dir)
    elif image_format == CBR_FORMAT:
        with rarfile.RarFile(filename, 'r') as rfile:
            rfile.extractall(tmp_dir)
    else:
        report = '%s %s is not a good format' % (filename, image_format)
        report_list = [report]
        bytes_diff = {'in': 0, 'out': 0}
        return (bytes_diff, report_list)

    if arguments.verbose:
        print('done')

    return os.path.basename(tmp_dir)


def optimize_comic_archive(filename_full, image_format, arguments, multiproc,
                           optimize_after):
    """ Optimize a comic archive """
    tmp_dir_basename = comic_archive_uncompress(filename_full,
                                                image_format, arguments)
    # recurse into comic archive even if flag not set
    archive_arguments = copy.deepcopy(arguments)
    archive_arguments.recurse = True
    archive_arguments.archive_name = os.path.basename(filename_full)

    # optimize contents of comic archive
    dirname = os.path.dirname(filename_full)
    result_set = optimize.optimize_files(dirname, [tmp_dir_basename],
                                         archive_arguments, multiproc,
                                         optimize_after)

    # I'd like to stuff this waiting into the compression process,
    # but process results don't serialize. :(
    for result in result_set:
        result.wait()

    args = (filename_full, multiproc['in'], multiproc['out'], arguments)
    return multiproc['pool'].apply_async(comic_archive_compress, args=(args,))
