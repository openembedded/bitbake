#
# Copyright (C) 2026 Agilent Technologies, Inc.
#
# SPDX-License-Identifier: GPL-2.0-only
#

import sys
import warnings

import bb.fetch

warnings.warn(
    "bb.fetch2 is deprecated; use bb.fetch instead",
    DeprecationWarning,
    stacklevel=2,
)

# Compatibility shim for code using bb.fetch2
sys.modules[__name__] = bb.fetch
