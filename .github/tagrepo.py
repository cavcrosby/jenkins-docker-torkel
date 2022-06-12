#!/usr/bin/env python3
"""Automatically tags repo based on changes that are expected."""
# Standard Library Imports
import argparse
import logging
import logging.config
import os
import pathlib
import re
import sys

# Third Party Imports
import autotag
from pylib.argparse import CustomHelpFormatter
from pylib.versions import (
    SemanticVersion,
    VersionUpdateTypes,
)

# Local Application Imports

# constants and other program configurations
_PROGNAME = os.path.basename(os.path.abspath(__file__))
_arg_parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=lambda prog: CustomHelpFormatter(
        prog, max_help_position=35
    ),
    allow_abbrev=False,
)

_DOCKERFILE = "Dockerfile"
_JENKINS_DOCKER_BASE_IMAGE = "cavcrosby/jenkins-base"
PRIOR_JENKINS_DOCKER_BASE_IMAGE_VERSION = (
    rf"(?<=-FROM ){_JENKINS_DOCKER_BASE_IMAGE}:v(.+)"  # noqa: E501,W503
)
CURRENT_JENKINS_DOCKER_BASE_IMAGE_VERSION = (
    rf"(?<=\+FROM ){_JENKINS_DOCKER_BASE_IMAGE}:v(.+)"  # noqa: E501,W503
)

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # noqa: E501,W503
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
            },
        },
        "loggers": {
            "": {"level": "INFO", "handlers": ["console"]},
        },
    }
)

_logger = logging.getLogger(__name__)


def retrieve_cmd_args():
    """Retrieve command arguments from the command line.

    Returns
    -------
    Namespace
        An object that holds attributes pulled from the command line.

    Raises
    ------
    SystemExit
        If user input is not considered valid when parsing arguments.

    """
    autotag_arg_parser = autotag.modify_arg_parser(_arg_parser)

    args = vars(autotag_arg_parser.parse_args())
    return args


def update_policy(patch, repo_working_dir):
    """Determine the update types in this repository from the previous commits.

    Parameters
    ----------
    patch : git.diff.DiffIndex
        The index of changes between two git commits.
    repo_working_dir : str
        The git working directory path.

    Returns
    -------
    repo_update_types : list of pylib.versions.VersionUpdateTypes
        The update types found from the changes.

    """
    repo_update_types = list()
    for chd_object in patch:
        chd_file_path = pathlib.PurePath(repo_working_dir).joinpath(
            chd_object.b_path
        )
        patch_text = chd_object.diff.decode("utf-8")

        if chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            _DOCKERFILE
        ) and re.findall(PRIOR_JENKINS_DOCKER_BASE_IMAGE_VERSION, patch_text):
            _logger.info(
                f"detected {_JENKINS_DOCKER_BASE_IMAGE} image version change "
                f"in {_DOCKERFILE}"
            )

            prior_base_img_version = SemanticVersion(
                re.findall(
                    PRIOR_JENKINS_DOCKER_BASE_IMAGE_VERSION, patch_text
                )[0]
            )
            current_base_img_version = SemanticVersion(
                re.findall(
                    CURRENT_JENKINS_DOCKER_BASE_IMAGE_VERSION, patch_text
                )[0]
            )
            _logger.info(
                f"prior image: {_JENKINS_DOCKER_BASE_IMAGE}:"
                f"{prior_base_img_version}"
            )
            _logger.info(
                f"current image: {_JENKINS_DOCKER_BASE_IMAGE}:"
                f"{current_base_img_version}"
            )

            base_img_update_types = (
                prior_base_img_version.determine_update_types(
                    current_base_img_version
                )
            )
            _logger.info(
                f"detected {_JENKINS_DOCKER_BASE_IMAGE} update types "
                f"between versions: {base_img_update_types}"
            )

            greatest_base_img_update_type = (
                SemanticVersion.determine_greatest_update_type(
                    base_img_update_types
                )
            )

            if greatest_base_img_update_type == VersionUpdateTypes.PATCH:
                repo_update_types.append(VersionUpdateTypes.PATCH)
            elif greatest_base_img_update_type == VersionUpdateTypes.MINOR:
                repo_update_types.append(VersionUpdateTypes.MINOR)
            elif greatest_base_img_update_type == VersionUpdateTypes.MAJOR:
                raise SystemExit(
                    "\n\n"
                    + f"WARNING: The current {_JENKINS_DOCKER_BASE_IMAGE} image has had a major version update.\n"  # noqa: E501,W503
                    + f"({_JENKINS_DOCKER_BASE_IMAGE}:{prior_base_img_version} -> {_JENKINS_DOCKER_BASE_IMAGE}:{current_base_img_version})\n"  # noqa: E501,W503
                    + "Manual tagging will need to occur for this kind of update.\n"  # noqa: E501,W503
                )
        elif chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            _DOCKERFILE
        ):
            _logger.info(f"detected general {_DOCKERFILE} changes")
            repo_update_types.append(VersionUpdateTypes.MINOR)
        elif chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            "child-casc.yaml"
        ):
            _logger.info("detected child-casc file changes")
            repo_update_types.append(VersionUpdateTypes.MINOR)
        elif chd_file_path == pathlib.PurePath(repo_working_dir).joinpath(
            "jobs.toml"
        ):
            _logger.info("detected jcascutil's Jenkins jobs file changes")
            repo_update_types.append(VersionUpdateTypes.MINOR)

    return repo_update_types


def main(args):
    """Start the main program execution."""
    _logger.info(f"started {_PROGNAME}")
    autotag.run(args, update_policy)


if __name__ == "__main__":
    args = retrieve_cmd_args()
    main(args)
    sys.exit(0)
