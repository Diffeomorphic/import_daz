import bpy
op = bpy.context.active_operator

op.files.clear()
op.useUnits = False
op.useExpressions = False
op.useVisemes = False
op.useHead = False
op.useFacs = True
op.useFacsdetails = True
op.useFacsexpr = True
op.useAnime = False
op.usePowerpose = True
op.useBody = False
op.useJcms = True
op.useFlexions = True
op.useBulges = False
op.bodyMaterial = "Body"

op.useMergeRigs = True
op.useApplyTransforms = True
op.useMergeMaterials = True
op.useBakedCorrectives = True
op.useDazFavorites = True
op.useTransferClothes = True
op.useTransferGeografts = True
op.useTransferFace = True
op.useMergeGeografts = True
op.useMakeAllBonesPosable = True
op.useFinalOptimization = False
