import bpy
op = bpy.context.active_operator

op.useUnits = True
op.useExpressions = True
op.useVisemes = True
op.useHead = True
op.useFacs = False
op.useFacsdetails = False
op.useFacsexpr = False
op.usePowerpose = False
op.useBody = False
op.useJcms = True
op.useFlexions = False
op.useBulges = False
op.bodyMaterial = "Torso"

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
