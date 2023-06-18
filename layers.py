# Copyright (c) 2016-2023, Thomas Larsson
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.

#-------------------------------------------------------------
#   MHX Layers
#-------------------------------------------------------------

L_MAIN =    0
L_SPINE =   1

L_LARMIK =  2
L_LARMFK =  3
L_LLEGIK =  4
L_LLEGFK =  5
L_LHAND =   6
L_LFINGER = 7
L_LEXTRA =  12
L_LTOE =    13

L_RARMIK =  18
L_RARMFK =  19
L_RLEGIK =  20
L_RLEGFK =  21
L_RHAND =   22
L_RFINGER = 23
L_REXTRA =  28
L_RTOE =    29

L_FACE =    8
L_TWEAK =   9
L_HEAD =    10
L_CUSTOM =  16

L_HELP =    14
L_HELP2 =   15
L_ORIG =    27
L_HIDE =    29
L_FIN =     30
L_DEF =     31

#-------------------------------------------------------------
#   Rigify Layers
#-------------------------------------------------------------

R_FACE = 1
R_DETAIL = 2
R_CUSTOM = 19
R_DEFORM = 29
R_HELP = 30
R_LAST = 31
R_FIN = 27

MhxRigifyLayer = {
    L_HELP : R_HELP,
    L_FACE : R_DETAIL,
    L_HEAD : R_FACE,
    L_CUSTOM : R_CUSTOM,
    L_FIN : R_LAST,
}

#-------------------------------------------------------------
#   Mha features
#-------------------------------------------------------------

F_TONGUE = 1
F_FINGER = 2