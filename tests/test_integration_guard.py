"""No-Docker regression tests for the disposable runner authorization guard."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent / "integration"
sys.path.insert(0, str(HERE))
from harness import refuse_unless_ephemeral  # noqa: E402


class EphemeralGuardTests(unittest.TestCase):
    def test_plain_local_environment_refused(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GitHub-hosted ephemeral runner"):
                refuse_unless_ephemeral()

    def test_self_hosted_runner_refused(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "RUNNER_ENVIRONMENT": "self-hosted",
            "RUNNER_OS": "Linux",
            "CI": "true",
            "MSC_DISPOSABLE_TEST_RUNNER": "isolated-ci-fixture-v1",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GitHub-hosted ephemeral runner"):
                refuse_unless_ephemeral()

    def test_custom_docker_endpoint_refused_even_with_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "GITHUB_ACTIONS": "true",
                "RUNNER_ENVIRONMENT": "github-hosted",
                "RUNNER_OS": "Linux",
                "CI": "true",
                "MSC_DISPOSABLE_TEST_RUNNER": "isolated-ci-fixture-v1",
                "GITHUB_WORKSPACE": str(HERE.parents[1]),
                "RUNNER_TEMP": tmp,
                "DOCKER_HOST": "tcp://127.0.0.1:2375",
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(RuntimeError, "custom Docker"):
                    refuse_unless_ephemeral()

    def test_runner_marker_alone_does_not_authorize(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "MSC_DISPOSABLE_TEST_RUNNER": "isolated-ci-fixture-v1",
                "GITHUB_WORKSPACE": str(HERE.parents[1]),
                "RUNNER_TEMP": tmp,
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(RuntimeError, "GitHub-hosted ephemeral runner"):
                    refuse_unless_ephemeral()


if __name__ == "__main__":
    unittest.main()
