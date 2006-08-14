#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2003, 2004  Phil Blundell
# Copyright (C) 2003 - 2005 Michael 'Mickey' Lauer
# Copyright (C) 2005        Holger Hans Peter Freyther
# Copyright (C) 2005        ROAD GmbH
# Copyright (C) 2006        Richard Purdie
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA 02111-1307 USA.

import os, re
from bb import data, utils
import bb

class NoProvider(Exception):
    """Exception raised when no provider can be found"""

def findBestProvider(pn, cfgData, dataCache, pkg_pn = None):
    """
    If there is a PREFERRED_VERSION, find the highest-priority bbfile
    providing that version.  If not, find the latest version provided by
    an bbfile in the highest-priority set.
    """
    if not pkg_pn:
        pkg_pn = dataCache.pkg_pn

    files = pkg_pn[pn]
    priorities = {}
    for f in files:
        priority = dataCache.bbfile_priority[f]
        if priority not in priorities:
            priorities[priority] = []
        priorities[priority].append(f)
    p_list = priorities.keys()
    p_list.sort(lambda a, b: a - b)
    tmp_pn = []
    for p in p_list:
        tmp_pn = [priorities[p]] + tmp_pn

    preferred_file = None

    localdata = data.createCopy(cfgData)
    bb.data.setVar('OVERRIDES', "%s:%s" % (pn, data.getVar('OVERRIDES', localdata)), localdata)
    bb.data.update_data(localdata)

    preferred_v = bb.data.getVar('PREFERRED_VERSION_%s' % pn, localdata, True)
    if preferred_v:
        m = re.match('(.*)_(.*)', preferred_v)
        if m:
            preferred_v = m.group(1)
            preferred_r = m.group(2)
        else:
            preferred_r = None

        for file_set in tmp_pn:
            for f in file_set:
                pv,pr = dataCache.pkg_pvpr[f]
                if preferred_v == pv and (preferred_r == pr or preferred_r == None):
                    preferred_file = f
                    preferred_ver = (pv, pr)
                    break
            if preferred_file:
                break;
        if preferred_r:
            pv_str = '%s-%s' % (preferred_v, preferred_r)
        else:
            pv_str = preferred_v
        if preferred_file is None:
            bb.msg.note(1, bb.msg.domain.Provider, "preferred version %s of %s not available" % (pv_str, pn))
        else:
            bb.msg.debug(1, bb.msg.domain.Provider, "selecting %s as PREFERRED_VERSION %s of package %s" % (preferred_file, pv_str, pn))

    del localdata

    # get highest priority file set
    files = tmp_pn[0]
    latest = None
    latest_p = 0
    latest_f = None
    for file_name in files:
        pv,pr = dataCache.pkg_pvpr[file_name]
        dp = dataCache.pkg_dp[file_name]

        if (latest is None) or ((latest_p == dp) and (utils.vercmp(latest, (pv, pr)) < 0)) or (dp > latest_p):
            latest = (pv, pr)
            latest_f = file_name
            latest_p = dp
    if preferred_file is None:
        preferred_file = latest_f
        preferred_ver = latest

    return (latest,latest_f,preferred_ver, preferred_file)

#
# RP - build_cache_fail needs to move elsewhere
#
def filterProviders(providers, item, cfgData, dataCache, build_cache_fail = {}):
    """
    Take a list of providers and filter/reorder according to the 
    environment variables and previous build results
    """
    eligible = []
    preferred_versions = {}

    # Collate providers by PN
    pkg_pn = {}
    for p in providers:
        pn = dataCache.pkg_fn[p]
        if pn not in pkg_pn:
            pkg_pn[pn] = []
        pkg_pn[pn].append(p)

    bb.msg.debug(1, bb.msg.domain.Provider, "providers for %s are: %s" % (item, pkg_pn.keys()))

    for pn in pkg_pn.keys():
        preferred_versions[pn] = bb.providers.findBestProvider(pn, cfgData, dataCache, pkg_pn)[2:4]
        eligible.append(preferred_versions[pn][1])


    for p in eligible:
        if p in build_cache_fail:
            bb.msg.debug(1, bb.msg.domain.Provider, "rejecting already-failed %s" % p)
            eligible.remove(p)

    if len(eligible) == 0:
        bb.error("no eligible providers for %s" % item)
        return 0

    # look to see if one of them is already staged, or marked as preferred.
    # if so, bump it to the head of the queue
    for p in providers:
        pn = dataCache.pkg_fn[p]
        pv, pr = dataCache.pkg_pvpr[p]

        stamp = '%s.do_populate_staging' % dataCache.stamp[p]
        if os.path.exists(stamp):
            (newvers, fn) = preferred_versions[pn]
            if not fn in eligible:
                # package was made ineligible by already-failed check
                continue
            oldver = "%s-%s" % (pv, pr)
            newver = '-'.join(newvers)
            if (newver != oldver):
                extra_chat = "%s (%s) already staged but upgrading to %s to satisfy %s" % (pn, oldver, newver, item)
            else:
                extra_chat = "Selecting already-staged %s (%s) to satisfy %s" % (pn, oldver, item)

            bb.msg.note(2, bb.msg.domain.Provider, "%s" % extra_chat)
            eligible.remove(fn)
            eligible = [fn] + eligible
            discriminated = True
            break

    return eligible

def getRuntimeProviders(dataCache, rdepend):
    """
    Return any providers of runtime dependency
    """
    rproviders = []

    if rdepend in dataCache.rproviders:
       rproviders += dataCache.rproviders[rdepend]

    if rdepend in dataCache.packages:
        rproviders += dataCache.packages[rdepend]

    if rproviders:
        return rproviders

    # Only search dynamic packages if we can't find anything in other variables
    for pattern in dataCache.packages_dynamic:
        regexp = re.compile(pattern)
        if regexp.match(rdepend):
            rproviders += dataCache.packages_dynamic[pattern]

    return rproviders
