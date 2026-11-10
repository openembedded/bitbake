"""
BitBake 'Fetch' implementation for Amazon AWS S3.

Class for fetching files from Amazon S3.

Two backends are provided and one is selected automatically when the module is
imported:

  S3Boto (preferred)
      Fetch in-process with the boto3 SDK, talking to S3 over HTTPS natively
      (no per-object subprocess / AWS CLI startup cost). This is a big win for
      sstate mirrors, where thousands of small objects are fetched and the AWS
      CLI's interpreter + config/credential resolution startup dominates wall
      time. Selected when boto3 is importable.

  S3CLI (fallback)
      Fetch by shelling out to the AWS CLI ("aws s3 cp" / "aws s3 ls"). This is
      the original behaviour and requires no extra Python packages; the aws
      tool must be installed and configured. Selected when boto3 is not
      importable, so there is no new hard dependency.

"""

# Copyright (C) 2017, Andre McCurdy <armccurdy@gmail.com>
#
# Based in part on bb.fetch.wget:
#    Copyright (C) 2003, 2004  Chris Larson
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Based on functions from the base bb module, Copyright 2003 Holger Schurig

import os
import bb
import time
import random
import urllib.request, urllib.parse, urllib.error
import re
import shlex
from bb.fetch import FetchMethod
from bb.fetch import FetchError
from bb.fetch import runfetchcmd

try:
    import boto3
    import botocore
except ImportError:
    boto3 = None


def convertToBytes(value, unit):
    value = float(value)
    if (unit == "KiB"):
        value = value*1024.0;
    elif (unit == "MiB"):
        value = value*1024.0*1024.0;
    elif (unit == "GiB"):
        value = value*1024.0*1024.0*1024.0;
    return value

class S3ProgressHandler(bb.progress.LineFilterProgressHandler):
    """
    Extract progress information from s3 cp output, e.g.:
    Completed 5.1 KiB/8.8 GiB (12.0 MiB/s) with 1 file(s) remaining
    """
    def __init__(self, d):
        super(S3ProgressHandler, self).__init__(d)
        # Send an initial progress event so the bar gets shown
        self._fire_progress(0)

    def writeline(self, line):
        percs = re.findall(r'^Completed (\d+.{0,1}\d*) (\w+)\/(\d+.{0,1}\d*) (\w+) (\(.+\)) with\s+', line)
        if percs:
            completed = (percs[-1][0])
            completedUnit = (percs[-1][1])
            total = (percs[-1][2])
            totalUnit = (percs[-1][3])
            completed = convertToBytes(completed, completedUnit)
            total = convertToBytes(total, totalUnit)
            progress = (completed/total)*100.0
            rate = percs[-1][4]
            self.update(progress, rate)
            return False
        return True


# Cache a single boto3 S3 client for the lifetime of the (worker) process.
# Creating a client resolves credentials and config once; reusing it keeps the
# underlying HTTPS connection pool warm across many small fetches.
#
# NOTE: bitbake runs setscene fetches in SEPARATE worker processes, so this
# cache is per-process, not global to the build. Credentials must come from a
# source that AUTO-REFRESHES, because a Yocto build runs for hours and any
# static/temporary credential (e.g. a fixed access key written into
# ~/.aws/credentials [default]) can EXPIRE partway through -- after which S3
# returns "400 Bad Request" on every call and all setscene tasks fail.
#
# The robust source is a `credential_process` profile: boto3 invokes it on
# demand and re-vends when the token nears expiry. We therefore resolve
# AWS_PROFILE from the bitbake datastore (or the environment) and pin it on the
# session, so the worker uses that auto-refreshing profile instead of a stale
# static [default]. Set AWS_PROFILE for the build (e.g. via
# BB_ENV_PASSTHROUGH_ADDITIONS so it survives bitbake's worker env scrubbing)
# to a profile whose [profile ...] entry in ~/.aws/config uses
# credential_process.
#
# A credential_process helper that caches vended credentials on disk will
# mostly serve them from that warm cache rather than from its backing service;
# the backoff below still covers a transient "Rate exceeded" during a
# cold-cache storm.
_s3_client = None

def _get_s3_client(d):
    global _s3_client
    if _s3_client is None:
        # Resolve region from the usual env vars; boto3 also honours
        # ~/.aws/config and AWS_CONFIG_FILE. (S3 handles cross-region HEAD/GET,
        # so an exact match is not required, but pinning avoids surprises.)
        region = (d.getVar("AWS_DEFAULT_REGION")
                  or os.environ.get("AWS_DEFAULT_REGION")
                  or os.environ.get("AWS_REGION"))
        # Resolve the AWS profile to use. Pinning it defeats a stale/expired
        # static [default] in ~/.aws/credentials shadowing the auto-refreshing
        # credential_process -- the exact cause of mid-build "400 Bad Request"
        # failures. d.getVar wins so it works even when the env is scrubbed in
        # a worker; env is the fallback when it is passed through.
        profile = (d.getVar("AWS_PROFILE")
                   or os.environ.get("AWS_PROFILE")
                   or os.environ.get("AWS_DEFAULT_PROFILE"))
        # Allow more concurrent connections than the default (10) so parallel
        # fetches within a process share a healthy pool. The 'retries' here
        # applies to S3 API calls only, NOT to credential resolution.
        cfg = botocore.config.Config(
            max_pool_connections=50,
            retries={"max_attempts": 5, "mode": "standard"},
        )

        # Credential resolution happens lazily on first API call OR eagerly in
        # client(); either way a credential_process "Rate exceeded" surfaces as
        # CredentialRetrievalError. Retry client creation + a cheap credential
        # resolution with exponential backoff + jitter so a transient
        # credential-service rate limit does not fail the whole setscene task.
        attempts = int(d.getVar("S3_CRED_MAX_ATTEMPTS") or 6)
        last_exc = None
        for attempt in range(attempts):
            try:
                session = boto3.session.Session(profile_name=profile, region_name=region)
                client = session.client("s3", config=cfg)
                # Force credential resolution now so we retry it here rather
                # than failing deep inside a download/head call.
                creds = session.get_credentials()
                # One-time-per-worker diagnostic: which credential source won,
                # the profile, and the region. Tells us whether the worker
                # picked the auto-refreshing credential_process profile or fell
                # back to a stale static default.
                try:
                    method = getattr(creds, "method", None) if creds else "NONE"
                    bb.debug(1, "S3 fetcher: credential method=%s profile=%s region=%s"
                             % (method, profile, client.meta.region_name))
                except Exception:
                    pass
                _s3_client = client
                break
            except botocore.exceptions.CredentialRetrievalError as e:
                last_exc = e
                if attempt == attempts - 1:
                    break
                # Exponential backoff with jitter: 0.5,1,2,4,8s (+/- jitter),
                # capped. Spreads out many workers refreshing credentials at once.
                delay = min(2.0 ** attempt * 0.5, 15.0)
                delay += random.uniform(0, delay / 2.0)
                bb.note("S3 fetcher: credential retrieval rate-limited "
                        "(attempt %d/%d), backing off %.1fs: %s"
                        % (attempt + 1, attempts, delay, e))
                time.sleep(delay)
        if _s3_client is None:
            raise FetchError("S3 fetcher could not obtain AWS credentials after "
                             "%d attempts. Set AWS_PROFILE to a profile whose "
                             "~/.aws/config entry uses credential_process (which "
                             "auto-refreshes), and ensure it is in the bitbake "
                             "env passthrough. Last error: %s"
                             % (attempts, last_exc))
    return _s3_client


class S3Common(FetchMethod):
    """Behaviour shared by the S3 fetcher backends (S3Boto and S3CLI)."""

    def supports(self, ud, d):
        """
        Check to see if a given url can be fetched with s3.
        """
        return ud.type in ['s3']

    def recommends_checksum(self, urldata):
        return True

    def urldata_init(self, ud, d):
        if 'downloadfilename' in ud.parm:
            ud.basename = ud.parm['downloadfilename']
        else:
            ud.basename = os.path.basename(ud.path)

        ud.localfile = ud.basename

    def download(self, ud, d):
        """
        Fetch urls
        Assumes localpath was called first
        """
        self._fetch(ud, d)

        # Additional sanity checks copied from the wget class (although there
        # are no known issues which mean these are required, treat the fetch
        # result with a little healthy suspicion).

        if not os.path.exists(ud.localpath):
            raise FetchError("The s3 fetch returned success for s3://%s%s but %s doesn't exist?!" % (ud.host, ud.path, ud.localpath))

        if os.path.getsize(ud.localpath) == 0:
            os.remove(ud.localpath)
            raise FetchError("The s3 fetch for s3://%s%s resulted in a zero size file?! Deleting and failing since this isn't right." % (ud.host, ud.path))

        return True


class S3Boto(S3Common):
    """Fetch urls in-process using the boto3 SDK."""

    def _fetch(self, ud, d):
        client = _get_s3_client(d)
        # ud.host is the bucket; ud.path starts with "/" so strip it for the
        # key. ud.path is percent-encoded (bitbake's mirror rewrite encodes the
        # ':' in sstate names as %3A); boto3 wants the RAW, decoded key and does
        # its own signing-time encoding, so decode here or S3 returns 400 Bad
        # Request from the double-encoding.
        bucket = ud.host
        key = urllib.parse.unquote(ud.path.lstrip('/'))

        bb.fetch.check_network_access(d, "boto3 get_object s3://%s/%s" % (bucket, key), ud.url)

        try:
            client.download_file(bucket, key, ud.localpath)
        except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
            raise FetchError("The boto3 download for s3://%s/%s failed: %s" % (bucket, key, e))

    def checkstatus(self, fetch, ud, d):
        """
        Check the status of a URL
        """
        client = _get_s3_client(d)
        bucket = ud.host
        # See _fetch: decode the percent-encoded key for boto3.
        key = urllib.parse.unquote(ud.path.lstrip('/'))

        bb.fetch.check_network_access(d, "boto3 head_object s3://%s/%s" % (bucket, key), ud.url)

        try:
            client.head_object(Bucket=bucket, Key=key)
        except botocore.exceptions.ClientError as e:
            # A 404 is an ordinary sstate miss (object not in the mirror) and is
            # expected for any task the mirror wasn't populated for -- log it at
            # debug level only so normal misses don't flood the console. Any
            # other code (400/403/5xx) is a real problem: surface it as a note.
            err = e.response.get("Error", {})
            meta = e.response.get("ResponseMetadata", {})
            status = meta.get("HTTPStatusCode")
            detail = ("head_object s3://%s/%s -> code=%s status=%s msg=%r reqid=%s"
                      % (bucket, key, err.get("Code"), status,
                         err.get("Message"), meta.get("RequestId")))
            if status == 404:
                bb.debug(2, "S3 fetcher: miss (404) s3://%s/%s" % (bucket, key))
            else:
                bb.note("S3 fetcher: %s" % detail)
            raise FetchError("The boto3 head_object for s3://%s/%s failed: %s" % (bucket, key, e))
        except botocore.exceptions.BotoCoreError as e:
            raise FetchError("The boto3 head_object for s3://%s/%s failed: %s" % (bucket, key, e))
        return True


class S3CLI(S3Common):
    """Fetch urls by shelling out to the AWS CLI ('aws s3')."""

    def urldata_init(self, ud, d):
        super().urldata_init(ud, d)
        ud.basecmd = shlex.split(d.getVar("FETCHCMD_s3") or "") or ["aws", "s3"]

    def _fetch(self, ud, d):
        cmd = ud.basecmd + ['cp', 's3://%s%s' % (ud.host, ud.path), ud.localpath]
        bb.fetch.check_network_access(d, cmd, ud.url)

        progresshandler = S3ProgressHandler(d)
        runfetchcmd(cmd, d, False, log=progresshandler)

    def checkstatus(self, fetch, ud, d):
        """
        Check the status of a URL
        """
        cmd = ud.basecmd + ['ls', 's3://%s%s' % (ud.host, ud.path)]
        bb.fetch.check_network_access(d, cmd, ud.url)
        output = runfetchcmd(cmd, d)

        # "aws s3 ls s3://mybucket/foo" will exit with success even if the file
        # is not found, so check output of the command to confirm success.
        if not output:
            raise FetchError("The aws ls command for s3://%s%s gave empty output" % (ud.host, ud.path))
        return True


# Pick the backend once, at import time: prefer boto3, fall back to the AWS CLI
# when boto3 is not importable. bb.fetch registers s3.S3, so this selection is
# transparent to the rest of bitbake.
if boto3 is not None:
    S3 = S3Boto
else:
    S3 = S3CLI
