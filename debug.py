# This file is for deprecated features, ideally we should not use them.

# GENERAL DEBUG
# If this option enabled, the entire addon is reloaded every time the user presses
# the F8 key. This is useful during development to reload modified files. If DEBUG is
# disabled Blender must be restarted for code changes to take effect.

DEBUG = True

# EXPERIMENTAL SUPPORT FOR ERC BONES IN MHX
# If you imported ERC morphs then MHX will try to preserve them
# usually ERC morphs are not supported for IK rigs
# this is not granted to work fine in production
#
# https://github.com/Diffeomorphic/import_daz/issues/61

DEBUG_MHX_ERC = False

# BACKWARD COMPATIBILITY FOR CUSTOM PROPERTIES
# The 4.4 version changed the way that custom properties are handled.
# As a result old characters (made before April 2025) may not work as expected.
# We need to reimport them or enable this feature for backward compatibility
#
# https://github.com/Diffeomorphic/import_daz/issues/88

OLD_STYLE_PROPS = False

