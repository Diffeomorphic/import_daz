import bpy
op = bpy.context.active_operator

op.useRigifyPose = False
op.useLimitConstraints = True
op.useFingerIk = False
op.tongueControl = 'NONE'
op.shaftControl = 'NONE'
op.shaftName = 'Shaft'
op.addNondeformExtras = True
op.keepRig = True
op.ikOptimization = 'POLE'
op.useAutoAlign = True
op.useRecalcRoll = False
op.useSplitShin = False
op.useCustomLayers = True
op.useDeleteMeta = True
