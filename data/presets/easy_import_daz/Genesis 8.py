import bpy
op = bpy.context.active_operator

op.useUnits = True
op.useExpressions = True
op.useVisemes = True
op.useHead = False
op.useFacs = False
op.useFacsdetails = False
op.useFacsexpr = False
op.useBody = False
op.useJcms = True
op.useFlexions = True
op.bodyMaterial = "Torso"

op.useEliminateEmpties = True
op.useMergeRigs = True
op.useApplyTransforms = True
op.useMergeMaterials = True
op.useFixShells = False
op.useMergeToes = False
op.useBakedCorrectives = True
op.useDazFavorites = True
op.useTransferClothes = True
op.useTransferGeografts = True
op.useTransferFace = True
op.useMergeGeografts = True
op.useMakeAllBonesPosable = True
op.useFinalOptimization = False

