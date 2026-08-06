# test/checkm2_testrun_test.py

import os
import subprocess
import unittest


class CheckM2TestrunTest(unittest.TestCase):
    """
    Smoke test for the CheckM2 installation inside the KBase image.

    This runs `checkm2 testrun` on the internal test genomes, as
    recommended by the CheckM2 docs, and just asserts that it
    completes successfully.
    """

    def test_checkm2_testrun_completes(self):
        # Path to the checkm2 executable inside your Docker image
        checkm2_bin = "/opt/conda/envs/checkm2/bin/checkm2"
        self.assertTrue(
            os.path.exists(checkm2_bin),
            f"{checkm2_bin} not found – did the conda env build correctly?",
        )

        # Where you downloaded the DB in the Dockerfile:
        #   checkm2 database --download --path /kb/module/data/checkm2_db
        db_path = "/kb/module/data/checkm2_db"
        self.assertTrue(
            os.path.isdir(db_path),
            f"CheckM2 DB path {db_path} does not exist",
        )

        # Optional working dir for temp / outputs
        work_dir = "/kb/module/work/checkm2_testrun"
        os.makedirs(work_dir, exist_ok=True)

        # Build the command – keep it simple
        cmd = [
            checkm2_bin,
            "testrun",
            "--threads",
            "2",
        ]

        # Make sure CheckM2 sees the DB; testrun uses internal genomes
        # but expects the DB location via env or config
        env = os.environ.copy()
        env.setdefault("CHECKM2DB", db_path)
        env.setdefault("TMPDIR", work_dir)

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        # Always print stdout so failures are visible in kb-sdk logs
        print("\n===== checkm2 testrun output =====")
        print(proc.stdout)
        print("===== end checkm2 testrun output =====\n")

        # Main assertion: command completed successfully
        self.assertEqual(
            proc.returncode,
            0,
            f"checkm2 testrun failed with exit code {proc.returncode}",
        )
