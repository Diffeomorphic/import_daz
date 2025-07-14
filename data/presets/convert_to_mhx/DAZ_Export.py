import bpy
op = bpy.context.active_operator

op.useImproveIk = False
op.useFingerIk = False
op.useTongueIk = False
op.driverRotationMode = 'NATIVE'
op.useTweakBones = False
op.showLinks = True
op.usePoleTargets = True
op.useStretch = False
op.useSpineIk = False
op.useShaftWinder = False
op.shaftName = 'Shaft'
op.elbowParent = 'SHOULDER'
op.kneeParent = 'MASTER'
op.useAnkleIk = False
op.keepG9Twist = True
op.boneGroups.clear()
op.useRaiseError = True
