import bpy
op = bpy.context.active_operator

op.useUnits = False
op.useExpressions = False
op.useVisemes = False
op.useHead = False
op.useFacs = False
op.useFacsdetails = False
op.useFacsexpr = False
op.useBody = False
op.useJcms = False
op.useBulges = False
op.useFlexions = False

op.useEliminateEmpties = False
op.useMergeRigs = True
op.useApplyTransforms = False
op.useMergeMaterials = True
op.useMergeToes = False
op.useBakedCorrectives = False
op.useDazFavorites = False
op.useTransferClothes = False
op.useTransferGeografts = False
op.useTransferFace = False
op.useMergeGeografts = False
op.useMakeAllBonesPosable = True
op.useFinalOptimization = False
