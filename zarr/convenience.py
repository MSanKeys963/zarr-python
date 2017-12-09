# -*- coding: utf-8 -*-
"""Convenience functions for storing and loading data."""
from __future__ import absolute_import, print_function, division
from collections import Mapping
import io
import re


from zarr.core import Array
from zarr.creation import open_array, normalize_store_arg, array as _create_array
from zarr.hierarchy import open_group, group as _create_group, Group
from zarr.storage import contains_array, contains_group
from zarr.errors import err_path_not_found
from zarr.util import normalize_storage_path, TreeViewer


# noinspection PyShadowingBuiltins
def open(store, mode='a', **kwargs):
    """Convenience function to open a group or array using file-mode-like semantics.

    Parameters
    ----------
    store : MutableMapping or string
        Store or path to directory in file system or name of zip file.
    mode : {'r', 'r+', 'a', 'w', 'w-'}, optional
        Persistence mode: 'r' means read only (must exist); 'r+' means
        read/write (must exist); 'a' means read/write (create if doesn't
        exist); 'w' means create (overwrite if exists); 'w-' means create
        (fail if exists).
    **kwargs
        Additional parameters are passed through to :func:`zarr.open_array` or
        :func:`zarr.open_group`.

    See Also
    --------
    zarr.open_array, zarr.open_group

    Examples
    --------

    Storing data in a directory 'data/example.zarr' on the local file system::

        >>> import zarr
        >>> store = 'data/example.zarr'
        >>> zw = zarr.open(store, mode='w', shape=100, dtype='i4')  # open new array
        >>> zw
        <zarr.core.Array (100,) int32>
        >>> za = zarr.open(store, mode='a')  # open existing array for reading and writing
        >>> za
        <zarr.core.Array (100,) int32>
        >>> zr = zarr.open(store, mode='r')  # open existing array read-only
        >>> zr
        <zarr.core.Array (100,) int32 read-only>
        >>> gw = zarr.open(store, mode='w')  # open new group, overwriting any previous data
        >>> gw
        <zarr.hierarchy.Group '/'>
        >>> ga = zarr.open(store, mode='a')  # open existing group for reading and writing
        >>> ga
        <zarr.hierarchy.Group '/'>
        >>> gr = zarr.open(store, mode='r')  # open existing group read-only
        >>> gr
        <zarr.hierarchy.Group '/' read-only>

    """

    path = kwargs.get('path', None)
    # handle polymorphic store arg
    store = normalize_store_arg(store, clobber=(mode == 'w'))
    path = normalize_storage_path(path)

    if mode in {'w', 'w-', 'x'}:
        if 'shape' in kwargs:
            return open_array(store, mode=mode, **kwargs)
        else:
            return open_group(store, mode=mode, **kwargs)

    elif mode == 'a':
        if contains_array(store, path):
            return open_array(store, mode=mode, **kwargs)
        elif contains_group(store, path):
            return open_group(store, mode=mode, **kwargs)
        elif 'shape' in kwargs:
            return open_array(store, mode=mode, **kwargs)
        else:
            return open_group(store, mode=mode, **kwargs)

    else:
        if contains_array(store, path):
            return open_array(store, mode=mode, **kwargs)
        elif contains_group(store, path):
            return open_group(store, mode=mode, **kwargs)
        else:
            err_path_not_found(path)


def save_array(store, arr, **kwargs):
    """Convenience function to save a NumPy array to the local file system, following a similar
    API to the NumPy save() function.

    Parameters
    ----------
    store : MutableMapping or string
        Store or path to directory in file system or name of zip file.
    arr : ndarray
        NumPy array with data to save.
    kwargs
        Passed through to :func:`create`, e.g., compressor.

    Examples
    --------
    Save an array to a directory on the file system (uses a :class:`DirectoryStore`)::

        >>> import zarr
        >>> import numpy as np
        >>> arr = np.arange(10000)
        >>> zarr.save_array('data/example.zarr', arr)
        >>> zarr.load('data/example.zarr')
        array([   0,    1,    2, ..., 9997, 9998, 9999])

    Save an array to a single file (uses a :class:`ZipStore`)::

        >>> zarr.save_array('data/example.zip', arr)
        >>> zarr.load('data/example.zip')
        array([   0,    1,    2, ..., 9997, 9998, 9999])

    """
    may_need_closing = isinstance(store, str)
    store = normalize_store_arg(store, clobber=True)
    try:
        _create_array(arr, store=store, overwrite=True, **kwargs)
    finally:
        if may_need_closing and hasattr(store, 'close'):
            # needed to ensure zip file records are written
            store.close()


def save_group(store, *args, **kwargs):
    """Convenience function to save several NumPy arrays to the local file system, following a
    similar API to the NumPy savez()/savez_compressed() functions.

    Parameters
    ----------
    store : MutableMapping or string
        Store or path to directory in file system or name of zip file.
    args : ndarray
        NumPy arrays with data to save.
    kwargs
        NumPy arrays with data to save.

    Examples
    --------
    Save several arrays to a directory on the file system (uses a :class:`DirectoryStore`)::

        >>> import zarr
        >>> import numpy as np
        >>> a1 = np.arange(10000)
        >>> a2 = np.arange(10000, 0, -1)
        >>> zarr.save_group('data/example.zarr', a1, a2)
        >>> loader = zarr.load('data/example.zarr')
        >>> loader
        <LazyLoader: arr_0, arr_1>
        >>> loader['arr_0']
        array([   0,    1,    2, ..., 9997, 9998, 9999])
        >>> loader['arr_1']
        array([10000,  9999,  9998, ...,     3,     2,     1])

    Save several arrays using named keyword arguments::

        >>> zarr.save_group('data/example.zarr', foo=a1, bar=a2)
        >>> loader = zarr.load('data/example.zarr')
        >>> loader
        <LazyLoader: bar, foo>
        >>> loader['foo']
        array([   0,    1,    2, ..., 9997, 9998, 9999])
        >>> loader['bar']
        array([10000,  9999,  9998, ...,     3,     2,     1])

    Store several arrays in a single zip file (uses a :class:`ZipStore`)::

        >>> zarr.save_group('data/example.zip', foo=a1, bar=a2)
        >>> loader = zarr.load('data/example.zip')
        >>> loader
        <LazyLoader: bar, foo>
        >>> loader['foo']
        array([   0,    1,    2, ..., 9997, 9998, 9999])
        >>> loader['bar']
        array([10000,  9999,  9998, ...,     3,     2,     1])

    Notes
    -----
    Default compression options will be used.

    """
    if len(args) == 0 and len(kwargs) == 0:
        raise ValueError('at least one array must be provided')
    # handle polymorphic store arg
    may_need_closing = isinstance(store, str)
    store = normalize_store_arg(store, clobber=True)
    try:
        grp = _create_group(store, overwrite=True)
        for i, arr in enumerate(args):
            k = 'arr_{}'.format(i)
            grp.create_dataset(k, data=arr, overwrite=True)
        for k, arr in kwargs.items():
            grp.create_dataset(k, data=arr, overwrite=True)
    finally:
        if may_need_closing and hasattr(store, 'close'):
            # needed to ensure zip file records are written
            store.close()


def save(store, *args, **kwargs):
    """Convenience function to save an array or group of arrays to the local file system.

    Parameters
    ----------
    store : MutableMapping or string
        Store or path to directory in file system or name of zip file.
    args : ndarray
        NumPy arrays with data to save.
    kwargs
        NumPy arrays with data to save.

    Examples
    --------
    Save an array to a directory on the file system (uses a :class:`DirectoryStore`)::

        >>> import zarr
        >>> import numpy as np
        >>> arr = np.arange(10000)
        >>> zarr.save('data/example.zarr', arr)
        >>> zarr.load('data/example.zarr')
        array([   0,    1,    2, ..., 9997, 9998, 9999])

    Save an array to a Zip file (uses a :class:`ZipStore`)::

        >>> zarr.save('data/example.zip', arr)
        >>> zarr.load('data/example.zip')
        array([   0,    1,    2, ..., 9997, 9998, 9999])

    Save several arrays to a directory on the file system (uses a
    :class:`DirectoryStore` and stores arrays in a group)::

        >>> import zarr
        >>> import numpy as np
        >>> a1 = np.arange(10000)
        >>> a2 = np.arange(10000, 0, -1)
        >>> zarr.save('data/example.zarr', a1, a2)
        >>> loader = zarr.load('data/example.zarr')
        >>> loader
        <LazyLoader: arr_0, arr_1>
        >>> loader['arr_0']
        array([   0,    1,    2, ..., 9997, 9998, 9999])
        >>> loader['arr_1']
        array([10000,  9999,  9998, ...,     3,     2,     1])

    Save several arrays using named keyword arguments::

        >>> zarr.save('data/example.zarr', foo=a1, bar=a2)
        >>> loader = zarr.load('data/example.zarr')
        >>> loader
        <LazyLoader: bar, foo>
        >>> loader['foo']
        array([   0,    1,    2, ..., 9997, 9998, 9999])
        >>> loader['bar']
        array([10000,  9999,  9998, ...,     3,     2,     1])

    Store several arrays in a single zip file (uses a :class:`ZipStore`)::

        >>> zarr.save('data/example.zip', foo=a1, bar=a2)
        >>> loader = zarr.load('data/example.zip')
        >>> loader
        <LazyLoader: bar, foo>
        >>> loader['foo']
        array([   0,    1,    2, ..., 9997, 9998, 9999])
        >>> loader['bar']
        array([10000,  9999,  9998, ...,     3,     2,     1])

    See Also
    --------
    save_array, save_group

    """
    if len(args) == 0 and len(kwargs) == 0:
        raise ValueError('at least one array must be provided')
    if len(args) == 1 and len(kwargs) == 0:
        save_array(store, args[0])
    else:
        save_group(store, *args, **kwargs)


class LazyLoader(Mapping):

    def __init__(self, grp):
        self.grp = grp
        self.cache = dict()

    def __getitem__(self, item):
        try:
            return self.cache[item]
        except KeyError:
            arr = self.grp[item][...]
            self.cache[item] = arr
            return arr

    def __len__(self):
        return len(self.grp)

    def __iter__(self):
        return iter(self.grp)

    def __contains__(self, item):
        return item in self.grp

    def __repr__(self):
        r = '<LazyLoader: '
        r += ', '.join(sorted(self.grp.array_keys()))
        r += '>'
        return r


def load(store):
    """Load data from an array or group into memory.

    Parameters
    ----------
    store : MutableMapping or string
        Store or path to directory in file system or name of zip file.

    Returns
    -------
    out
        If the store contains an array, out will be a numpy array. If the store contains a group,
        out will be a dict-like object where keys are array names and values are numpy arrays.

    See Also
    --------
    save, savez

    Notes
    -----
    If loading data from a group of arrays, data will not be immediately loaded into memory.
    Rather, arrays will be loaded into memory as they are requested.

    """
    # handle polymorphic store arg
    store = normalize_store_arg(store)
    if contains_array(store, path=None):
        return Array(store=store, path=None)[...]
    elif contains_group(store, path=None):
        grp = Group(store=store, path=None)
        return LazyLoader(grp)


class _LogWriter(object):

    def __init__(self, log):
        self.log_func = None
        self.log_file = None
        self.needs_closing = False
        if log is None:
            # don't do any logging
            pass
        elif callable(log):
            self.log_func = log
        elif isinstance(log, str):
            self.log_file = io.open(log, mode='w')
            self.needs_closing = True
        else:
            if not hasattr(log, 'write'):
                raise TypeError('log must be a callable function, file path or file-like '
                                'object, found %r' % log)
            self.log_file = log
            self.needs_closing = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.log_file is not None and self.needs_closing:
            self.log_file.close()

    def __call__(self, *args, **kwargs):
        if self.log_file is not None:
            kwargs['file'] = self.log_file
            print(*args, **kwargs)
            if hasattr(self.log_file, 'flush'):
                # get immediate feedback
                self.log_file.flush()
        elif self.log_func is not None:
            self.log_func(*args, **kwargs)


def copy_store(source, dest, source_path='', dest_path='', excludes=None,
               includes=None, flags=0, log=None):
    """Copy data directly from the `source` store to the `dest` store. Use this
    function when you want to copy a group or array in the most efficient way,
    preserving all configuration and attributes. This function is more efficient
    than the copy() or copy_all() functions because it avoids de-compressing and
    re-compressing data, rather the compressed chunk data for each array are copied
    directly between stores.

    Parameters
    ----------
    source : Mapping
        Store to copy data from.
    dest : MutableMapping
        Store to copy data into.
    source_path : str, optional
        Only copy data from under this path in the source store.
    dest_path : str, optional
        Copy data into this path in the destination store.
    excludes : sequence of str, optional
        One or more regular expressions which will be matched against keys in the
        source store. Any matching key will not be copied.
    includes : sequence of str, optional
        One or more regular expressions which will be matched against keys in the
        source store and will override any excludes also matching.
    flags : int, optional
        Regular expression flags used for matching excludes and includes.
    log : callable, file path or file-like object, optional
        If provided, will be used to log progress information.

    Examples
    --------
    >>> import zarr
    >>> store1 = zarr.DirectoryStore('data/example.zarr')
    >>> root = zarr.group(store1, overwrite=True)
    >>> foo = root.create_group('foo')
    >>> bar = foo.create_group('bar')
    >>> baz = bar.create_dataset('baz', shape=100, chunks=50, dtype='i8')
    >>> import numpy as np
    >>> baz[:] = np.arange(100)
    >>> root.tree()
    /
     └── foo
         └── bar
             └── baz (100,) int64
    >>> import sys
    >>> store2 = zarr.ZipStore('data/example.zip', mode='w')  # or any type of store
    >>> zarr.copy_store(store1, store2, log=sys.stdout)
    .zgroup -> .zgroup
    foo/.zgroup -> foo/.zgroup
    foo/bar/.zgroup -> foo/bar/.zgroup
    foo/bar/baz/.zarray -> foo/bar/baz/.zarray
    foo/bar/baz/0 -> foo/bar/baz/0
    foo/bar/baz/1 -> foo/bar/baz/1
    >>> new_root = zarr.group(store2)
    >>> new_root.tree()
    /
     └── foo
         └── bar
             └── baz (100,) int64
    >>> new_root['foo/bar/baz'][:]
    array([ 0,  1,  2,  ..., 97, 98, 99])
    >>> store2.close()  # zip stores need to be closed

    """

    # normalize paths
    source_path = normalize_storage_path(source_path)
    dest_path = normalize_storage_path(dest_path)
    if source_path:
        source_path = source_path + '/'
    if dest_path:
        dest_path = dest_path + '/'

    # normalize excludes and includes
    if excludes is None:
        excludes = []
    elif isinstance(excludes, str):
        excludes = [excludes]
    if includes is None:
        includes = []
    elif isinstance(includes, str):
        includes = [includes]
    excludes = [re.compile(e, flags) for e in excludes]
    includes = [re.compile(i, flags) for i in includes]

    # setup logging
    with _LogWriter(log) as log:

        # iterate over source keys
        for source_key in sorted(source.keys()):

            # filter to keys under source path
            if source_key.startswith(source_path):

                # process excludes and includes
                exclude = False
                for prog in excludes:
                    if prog.search(source_key):
                        exclude = True
                        break
                if exclude:
                    for prog in includes:
                        if prog.search(source_key):
                            exclude = False
                            break
                if exclude:
                    continue

                # map key to destination path
                key_suffix = source_key[len(source_path):]
                dest_key = dest_path + key_suffix

                # retrieve and copy data
                log('{} -> {}'.format(source_key, dest_key))
                dest[dest_key] = source[source_key]


def copy(source, dest, name=None, shallow=False, without_attrs=False, log=None,
         **create_kws):
    """Copy the `source` array or group into the `dest` group.

    Parameters
    ----------
    source : group or array/dataset
        A zarr group or array, or an h5py group or dataset.
    dest : group
        A zarr or h5py group.
    name : str, optional
        Name to copy the object to.
    shallow : bool, optional
        If True, only copy immediate children of `source`.
    without_attrs : bool, optional
        Do not copy user attributes.
    log : callable, file path or file-like object, optional
        If provided, will be used to log progress information.
    **create_kws
        Passed through to the create_dataset method when copying an array/dataset.

    Examples
    --------
    >>> import h5py
    >>> import zarr
    >>> import numpy as np
    >>> source = h5py.File('data/example.h5', mode='w')
    >>> foo = source.create_group('foo')
    >>> baz = foo.create_dataset('bar/baz', data=np.arange(100), chunks=(50,))
    >>> spam = source.create_dataset('spam', data=np.arange(100, 200), chunks=(30,))
    >>> zarr.tree(source)
    /
     ├── foo
     │   └── bar
     │       └── baz (100,) int64
     └── spam (100,) int64
    >>> dest = zarr.group()
    >>> import sys
    >>> zarr.copy(source['foo'], dest, log=sys.stdout)
    /foo -> /foo
    /foo/bar -> /foo/bar
    /foo/bar/baz -> /foo/bar/baz
    >>> dest.tree()  # N.B., no spam
    /
     └── foo
         └── bar
             └── baz (100,) int64

    """

    # setup logging
    with _LogWriter(log) as log:
        _copy(log, source, dest, name=name, root=True, shallow=shallow,
              without_attrs=without_attrs, **create_kws)


def _copy(log, source, dest, name, root, shallow, without_attrs, **create_kws):

    # are we copying to/from h5py?
    source_h5py = source.__module__.startswith('h5py.')
    dest_h5py = dest.__module__.startswith('h5py.')

    # determine name to copy to
    if name is None:
        name = source.name.split('/')[-1]
        if not name:
            raise TypeError('source has no name, please provide the `name` '
                            'parameter to indicate a name to copy to')

    if hasattr(source, 'shape'):
        # copy a dataset/array

        # setup creation keyword arguments
        kws = create_kws.copy()

        # setup chunks option, preserve by default
        kws.setdefault('chunks', source.chunks)

        # setup compression options
        if source_h5py:
            if dest_h5py:
                # h5py -> h5py; preserve compression options by default
                kws.setdefault('compression', source.compression)
                kws.setdefault('compression_opts', source.compression_opts)
                kws.setdefault('shuffle', source.shuffle)
            else:
                # h5py -> zarr; use zarr default compression options
                pass
        else:
            if dest_h5py:
                # zarr -> h5py; use some vaguely sensible defaults
                kws.setdefault('compression', 'gzip')
                kws.setdefault('compression_opts', 1)
                kws.setdefault('shuffle', True)
            else:
                # zarr -> zarr; preserve compression options by default
                kws.setdefault('compressor', source.compressor)

        # create new dataset in destination
        ds = dest.create_dataset(name, shape=source.shape, dtype=source.dtype, **kws)

        # copy data - N.B., if dest is h5py this will load all data into memory
        log('{} -> {}'.format(source.name, ds.name))
        ds[:] = source

        # copy attributes
        if not without_attrs:
            ds.attrs.update(source.attrs)

    elif root or not shallow:
        # copy a group

        # creat new group in destination
        grp = dest.create_group(name)
        log('{} -> {}'.format(source.name, grp.name))

        # copy attributes
        if not without_attrs:
            grp.attrs.update(source.attrs)

        # recurse
        for k in source.keys():
            _copy(log, source[k], grp, name=k, root=False, shallow=shallow,
                  without_attrs=without_attrs, **create_kws)


def tree(grp, expand=False, level=None):
    """Provide a ``print``-able display of the hierarchy. This function is provided
    mainly as a convenience for obtaining a tree view of an h5py group - zarr groups
    have a ``.tree()`` method.

    Parameters
    ----------
    grp : Group
        Zarr or h5py group.
    expand : bool, optional
        Only relevant for HTML representation. If True, tree will be fully expanded.
    level : int, optional
        Maximum depth to descend into hierarchy.

    Examples
    --------
    >>> import zarr
    >>> g1 = zarr.group()
    >>> g2 = g1.create_group('foo')
    >>> g3 = g1.create_group('bar')
    >>> g4 = g3.create_group('baz')
    >>> g5 = g3.create_group('qux')
    >>> d1 = g5.create_dataset('baz', shape=100, chunks=10)
    >>> g1.tree()
    /
     ├── bar
     │   ├── baz
     │   └── qux
     │       └── baz (100,) float64
     └── foo
    >>> import h5py
    >>> h5f = h5py.File('data/example.h5', mode='w')
    >>> zarr.copy_all(g1, h5f)
    >>> zarr.tree(h5f)
    /
     ├── bar
     │   ├── baz
     │   └── qux
     │       └── baz (100,) float64
     └── foo

    See Also
    --------
    zarr.hierarchy.Group.tree

    """

    return TreeViewer(grp, expand=expand, level=level)


def copy_all(source, dest, shallow=False, without_attrs=False, log=None, **create_kws):
    """Copy all children of the `source` group into the `dest` group.

    Parameters
    ----------
    source : group or array/dataset
        A zarr group or array, or an h5py group or dataset.
    dest : group
        A zarr or h5py group.
    shallow : bool, optional
        If True, only copy immediate children of `source`.
    without_attrs : bool, optional
        Do not copy user attributes.
    log : callable, file path or file-like object, optional
        If provided, will be used to log progress information.
    **create_kws
        Passed through to the create_dataset method when copying an array/dataset.

    Examples
    --------
    >>> import h5py
    >>> import zarr
    >>> import numpy as np
    >>> source = h5py.File('data/example.h5', mode='w')
    >>> foo = source.create_group('foo')
    >>> baz = foo.create_dataset('bar/baz', data=np.arange(100), chunks=(50,))
    >>> spam = source.create_dataset('spam', data=np.arange(100, 200), chunks=(30,))
    >>> zarr.tree(source)
    /
     ├── foo
     │   └── bar
     │       └── baz (100,) int64
     └── spam (100,) int64
    >>> dest = zarr.group()
    >>> import sys
    >>> zarr.copy_all(source, dest, log=sys.stdout)
    /foo -> /foo
    /foo/bar -> /foo/bar
    /foo/bar/baz -> /foo/bar/baz
    /spam -> /spam
    >>> dest.tree()
    /
     ├── foo
     │   └── bar
     │       └── baz (100,) int64
     └── spam (100,) int64

    """

    # setup logging
    with _LogWriter(log) as log:
        for k in source.keys():
            _copy(log, source[k], dest, name=k, root=False, shallow=shallow,
                  without_attrs=without_attrs, **create_kws)
