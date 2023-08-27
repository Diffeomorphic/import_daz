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
op.useJcms = False
op.useFlexions = False
op.bodyMaterial = "Torso"

op.useEliminateEmpties = True
op.useMergeRigs = True
op.useApplyTransforms = True
op.useMergeMaterials = True
op.useFixShells = True
op.useMergeToes = False
op.useBakedCorrectives = False
op.useDazFavorites = True
op.useTransferClothes = True
op.useTransferGeografts = True
op.useTransferFace = True
op.useSoftbody = False
op.useMergeGeografts = True
op.useMakeAllBonesPosable = True
op.useFinalOptimization = True
