# SPDX-FileCopyrightText: 2016-2025, Thomas Larsson
#
# SPDX-License-Identifier: GPL-2.0-or-later

from urllib.parse import unquote
from .error import DazError
from .settings import GS, LS

#----------------------------------------------------------
#   Api functions available for external scripting
#----------------------------------------------------------

def get_error_message():
    """get_error_message()

    Get the current error message.

    Returns:
    The error message from previous operator invokation if it raised
    an error, or the empty string if the operator exited without errors.
    """
    return LS.message


def get_silent_mode():
    return GS.silentMode


def set_silent_mode(value):
    """set_silent_mode(value)

    In silent mode, operators fail silently if they encounters an error.
    This is useful for scripting.

    Arguments:
    ?value: True turns silent mode on, False turns it off.
    """
    GS.silentMode = value


def get_morphs(ob, morphset, category=None, activeOnly=False):
    """get_morphs(ob, type, category=None, activeOnly=False)
    Get all morph names and values of the specified type from the object.

    Returns:
    A dictonary of morph names - morph values for all morphs in the specified morphsets.

    Arguments:
    ?ob: Object (armature or mesh) which owns the morphs

    ?type: Either a string in ["Units", "Expressions", "Visemes", "Facs", "Facsexpr", "Body", "Custom", "Jcms", "Flexions"],
        or a list of such strings, or the keyword "All" signifying all morphset in the list.

    ?category (optional): The category name for Custom morphs.

    ?activeOnly (optional): Active morphs only (default False).
    """
    from .morphing import getMorphsExternal
    return getMorphsExternal(ob, morphset, category, activeOnly)


def get_return_value():
    """get_return_value()
    Get value returned by previous operator.

    Returns:
    A dictonary of return values. For operators that import morphs, this dictionary is of the form {Lowercase filepath : Property name}.
    """
    return LS.returnValue


def get_canonical_filepath(filepath):
    """get_canonical_filepath(filepath)
    Return a canonical form of the filepath, which can be used to index the return value dict.

    Returns:
    The canonical filepath, or None if this can not be constructed.

    Arguments:
    ?filepath: String which represents a filepath
    """
    from .load_morph import getCanonicalFilePath
    return getCanonicalFilePath(unquote(filepath))

#-------------------------------------------------------------
#   Get and set global setting
#-------------------------------------------------------------

def get_global_setting(setting):
    """get_global_setting(setting)

    Returns:
    The value of the global setting "setting", or None if that is missing.

    Arguments:
    ?setting: Name of the global setting
    """
    return (getattr(GS, setting) if hasattr(GS, setting) else None)


def set_global_setting(setting, value):
    """set_global_setting(setting, value)

    Returns:
    Sets the value of the global setting "setting".

    Arguments:
    ?setting: Name of the global setting
    ?value: New value of the global setting
    """
    try:
        setattr(GS, setting, value)
    except:
        pass

#-------------------------------------------------------------
#   Active file paths used from python
#-------------------------------------------------------------

def clear_selection():
    """clear_selection()

    Clear the active file selection to be loaded by consecutive operators.
    """
    LS.filepaths = []
    print("File paths cleared")


def get_selection():
    """get_selection()

    Get the active file selection to be loaded by consecutive operators.

    Returns:
    The active list of file paths (strings).
    """
    return LS.filepaths


def set_selection(files):
    """set_selection(files)

    Set the active file selection to be loaded by consecutive operators.

    Arguments:
    ?files: A list of file paths (strings).
    """
    if isinstance(files, list):
        LS.filepaths = [file.replace("\\", "/") for file in files]
    else:
        try:
            raise DazError("File paths must be a list of strings")
        except:
            pass

def update_drivers(ob):
    """update_drivers(ob)

    Update drivers of the specified object

    Arguments:
    ?ob: Object
    """
    from .utils import updateDrivers
    updateDrivers(ob)
    updateDrivers(ob.data)


def set_slider(ob, prop, value):
    """set_slider(ob, prop, value)

    Set slider value, like ob[prop] = value,
    but taking aliases into account.

    Arguments:
    ?ob: Object that owns slider
    ?prop: Property name
    ?value: Property value
    """
    ob[prop] = value
    if prop in dazRna(ob).DazAlias.keys():
        alias = dazRna(ob).DazAlias[prop].s
        ob[alias] = value

#-------------------------------------------------------------
#   Access to paths relative to root directories
#-------------------------------------------------------------

def get_root_paths():
    """get_root_paths()

    Get the DAZ root paths

    Returns:
    The list of DAZ root paths
    """
    return GS.getDazPaths()


def get_absolute_paths(paths):
    """get_absolute_paths()

    Get the absolute filepaths corresponding to the given relative filepaths.

    Arguments:
    ?paths: Paths or references relative to the DAZ root paths.

    Returns:
    The corresponding absolute paths if they exist.
    """
    GS.setRootPaths()
    abspaths = []
    for path in paths:
        path = path.replace("\\", "/")
        abspath = GS.getAbsPath(path)
        if abspath:
            abspaths.append(abspath)
    return abspaths

#-------------------------------------------------------------
#   Load DAZ file
#-------------------------------------------------------------

def load_daz_file(filepath):
    """load_daz_file(filepath)

    Import a duf/dsf file (a gzipped json file).

    Arguments:
    ?filepath: File path

    Returns:
    The content of the file as a Python dict.
    """
    from .load_json import JL
    return JL.load(filepath)

#-------------------------------------------------------------
#   Paths used by Xin's HD-morphs add-on
#-------------------------------------------------------------

def get_default_morph_directories(ob):
    from .fileutils import getFoldersFromObject
    return getFoldersFromObject(ob, ["Morphs/"])

def get_dhdm_directories(ob=None):
    from .fileutils import getHDDirs
    return getHDDirs(ob, "DazDhdmFiles")

def get_morph_directories(ob=None):
    from .fileutils import getHDDirs
    return getHDDirs(ob, "DazMorphFiles")

