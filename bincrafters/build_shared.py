#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import platform
from six import string_types
from cpt.packager import ConanMultiPackager
from cpt.tools import split_colon_env


def get_bool_from_env(var_name, default="1"):
    val = os.getenv(var_name, default)
    return str(val).lower() in ("1", "true", "yes", "y")

def get_value_from_recipe(search_string, recipe="conanfile.py"):
    with open(recipe, "r") as conanfile:
        contents = conanfile.read()
        result = re.search(search_string, contents)
    return result


def get_name_from_recipe():
    return get_value_from_recipe(r'''name\s*=\s*["'](\S*)["']''').groups()[0]


def get_version_from_recipe():
    return get_value_from_recipe(r'''version\s*=\s*["'](\S*)["']''').groups()[0]


def is_shared():
    match = get_value_from_recipe(r'''options.*=([\s\S]*?)(?=}|$)''')
    if match is None:
        return False
    return "shared" in match.groups()[0]


def is_ci_running():
    result = os.getenv("APPVEYOR_REPO_NAME", False) or \
             os.getenv("TRAVIS_REPO_SLUG", False) or \
             os.getenv("CIRCLECI", False)
    return result != False


def get_repo_name_from_ci():
    reponame_a = os.getenv("APPVEYOR_REPO_NAME", "")
    reponame_t = os.getenv("TRAVIS_REPO_SLUG", "")
    reponame_c = "%s/%s" % (os.getenv("CIRCLE_PROJECT_USERNAME", ""),
                            os.getenv("CIRCLE_PROJECT_REPONAME", ""))
    return reponame_a or reponame_t or reponame_c


def get_repo_branch_from_ci():
    repobranch_a = os.getenv("APPVEYOR_REPO_BRANCH", "")
    repobranch_t = os.getenv("TRAVIS_BRANCH", "")
    repobranch_c = os.getenv("CIRCLE_BRANCH", "")
    return repobranch_a or repobranch_t or repobranch_c


def get_ci_vars():
    reponame = get_repo_name_from_ci()
    reponame_split = reponame.split("/")

    repobranch = get_repo_branch_from_ci()
    repobranch_split = repobranch.split("/")

    username, _ = reponame_split if len(reponame_split) > 1 else ["", ""]
    channel, version = repobranch_split if len(repobranch_split) > 1 else ["", ""]
    return username, channel, version


def get_username_from_ci():
    username, _, _ = get_ci_vars()
    return username


def get_channel_from_ci():
    _, channel, _ = get_ci_vars()
    return channel


def get_version_from_ci():
    _, _, version = get_ci_vars()
    return version


def get_version():
    ci_ver = get_version_from_ci()
    return ci_ver if ci_ver else get_version_from_recipe()


def get_conan_vars():
    username = os.getenv("CONAN_USERNAME", get_username_from_ci() or "bincrafters")
    channel = os.getenv("CONAN_CHANNEL", get_channel_from_ci())
    version = os.getenv("CONAN_VERSION", get_version())
    login_username = os.getenv("CONAN_LOGIN_USERNAME", username)
    return username, channel, version, login_username


def get_user_repository(username, repository_name):
    return "https://api.bintray.com/conan/{0}/{1}".format(username.lower(), repository_name)


def get_conan_upload(username):
    repository_name = os.getenv("BINTRAY_REPOSITORY", "public-conan")
    return os.getenv("CONAN_UPLOAD", get_user_repository(username, repository_name)).split('@')


def get_conan_remotes(username):
    remotes = os.getenv("CONAN_REMOTES")
    if not remotes:
        # While redundant, this moves upload remote to position 0.
        remotes = [get_conan_upload(username)]

        # Add bincrafters repository for other users, e.g. if the package would
        # require other packages from the bincrafters repo.
        bincrafters_user = "bincrafters"
        if username != bincrafters_user:
            remotes.append(get_conan_upload(bincrafters_user))
    if isinstance(remotes, string_types):
        remotes.split('@')
    return remotes


def get_upload_when_stable():
    return get_bool_from_env("CONAN_UPLOAD_ONLY_WHEN_STABLE")


def get_os():
    return platform.system().replace("Darwin", "Macos")


def get_archs():
    archs = os.getenv("CONAN_ARCHS", None)
    if get_os() == "Macos" and archs is None:
        return ["x86_64"]
    return split_colon_env("CONAN_ARCHS") if archs else None

def get_builder(build_policy=None):
    name = get_name_from_recipe()
    username, channel, version, login_username = get_conan_vars()
    reference = "{0}/{1}".format(name, version)
    upload = get_conan_upload(username)
    remotes = get_conan_remotes(username)
    upload_when_stable = get_upload_when_stable()
    stable_branch_pattern = os.getenv("CONAN_STABLE_BRANCH_PATTERN", "stable/*")
    archs = get_archs()
    build_policy = os.getenv('CONAN_BUILD_POLICY', build_policy)
    builder = ConanMultiPackager(
        username=username,
        login_username=login_username,
        channel=channel,
        reference=reference,
        upload=upload,
        remotes=remotes,
        archs=archs,
        build_policy=build_policy,
        upload_only_when_stable=upload_when_stable,
        stable_branch_pattern=stable_branch_pattern)

    return builder
