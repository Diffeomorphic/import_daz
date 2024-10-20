import bpy
op = bpy.context.active_operator

op.files.clear()
op.useUnits = False
op.useExpressions = False
op.useVisemes = False
op.useHead = False
op.useFacs = True
op.useFacsdetails = False
op.useFacsexpr = True
op.useAnime = True
op.useBody = False
op.useJcms = False
op.useFlexions = True
op.useBulges = False
op.bodyMaterial = "Body"

op.useMergeRigs = True
op.useMergeMaterials = True
op.useBakedCorrectives = True
op.useDazFavorites = True
op.useTransferClothes = True
op.useTransferGeografts = True
op.useTransferFace = True
op.useMergeGeografts = True
op.useMakeAllBonesPosable = True
op.useFinalOptimization = False
