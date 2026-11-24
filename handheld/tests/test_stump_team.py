#!/usr/bin/env python3
"""stump_team.py: the handheld Stump's packs and identity by Team Stump's own
code (its SandBox_Stump_On clone's provisioner.py, 1.0.0-beta.75 and .76).
With STUMP_ON=path/to/SandBox_Stump_On, Team Stump's real code runs.
    python3 handheld/tests/test_stump_team.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import stump_team as T  # noqa: E402


class TeamStumpsCode(unittest.TestCase):
    def setUp(self):
        os.environ.pop("SANDBOX_DIR", None)
        self.home = tempfile.mkdtemp(prefix="home-")
        self.addCleanup(shutil.rmtree, self.home, True)
        self.folder = self.stump("Stump", "Hazel", bytes(range(64)))

    def stump(self, name, node, key):
        folder = os.path.join(self.home, name)
        os.makedirs(os.path.join(folder, "rns"))
        open(os.path.join(folder, "stump_pc.py"), "w").close()
        with open(os.path.join(folder, "config.py"), "w") as f:
            f.write("NODE_NAME = '%s'\n" % node)
        with open(os.path.join(folder, "rns", "identity"), "wb") as f:
            f.write(key)
        return folder

    def test_no_clone_yet(self):
        self.assertIn("No SandBox_Stump_On", T.team("packs", self.folder, home=self.home)["error"])

    def test_an_older_clone(self):
        os.makedirs(os.path.join(self.home, "SandBox_Stump_On"))
        with open(os.path.join(self.home, "SandBox_Stump_On", "provisioner.py"), "w") as f:
            f.write("print('an old wizard')\n")
        self.assertEqual(T.team("packs", self.folder, home=self.home), {"old": "1.0.0-beta.75"})
        self.assertEqual(T.team("save", self.folder, home=self.home, dir=self.home), {"old": "1.0.0-beta.76"})
        self.assertEqual(T.team("stamps", self.folder, home=self.home), {"old": "1.0.0-beta.86"})

    def test_its_own_python(self):
        self.assertEqual(T.python_for(self.folder), sys.executable)
        py = os.path.join(self.folder, "venv", "bin", "python")
        os.makedirs(os.path.dirname(py))
        open(py, "w").close()
        self.assertEqual(T.python_for(self.folder), py)

    @unittest.skipUnless(os.environ.get("STUMP_ON"), "STUMP_ON=path/to/SandBox_Stump_On runs Team Stump's code")
    def test_packs_and_identity(self):
        os.symlink(os.path.abspath(os.environ["STUMP_ON"]), os.path.join(self.home, "SandBox_Stump_On"))
        r = T.team("packs", self.folder, home=self.home)
        if r.get("old"):
            self.skipTest("STUMP_ON is older than %s" % r["old"])
        self.assertIn("tavern", [x["name"] for x in r["rows"]], r)
        self.assertTrue(all(x["state"] == "new" for x in r["rows"]))
        r = T.team("install", self.folder, home=self.home, name="tavern")
        self.assertTrue(r["ok"], r)
        row = next(x for x in r["rows"] if x["name"] == "tavern")
        self.assertEqual((row["state"], row["here"]), ("same", row["version"]))
        self.assertEqual(T.keeps_text(row), "its saved data, its theme (tavern)")
        with open(os.path.join(self.folder, "tavern", ".from_pack")) as f:
            self.assertEqual(json.load(f)["pack"], "tavern")
        r = T.team("remove", self.folder, home=self.home, name="tavern", also=False)
        self.assertTrue(r["ok"], r)
        self.assertFalse(os.path.exists(os.path.join(self.folder, "tavern")))
        # Its identity: saved (never over another file), found, brought back (the one it had kept first).
        r1 = T.team("save", self.folder, home=self.home, dir=self.home)
        r2 = T.team("save", self.folder, home=self.home, dir=self.home)
        self.assertEqual([os.path.basename(r1["path"]), os.path.basename(r2["path"])],
                         ["Hazel.stump-identity", "Hazel (2).stump-identity"])
        elm = T.team("save", self.stump("Elm", "Elm", bytes(64)), home=self.home, dir=self.home)["path"]
        self.assertIn(elm, T.keepsakes([self.home], self.home))
        r = T.team("restore", self.folder, home=self.home, src=elm, keep=self.home)
        self.assertEqual(r["name"], "Elm", r)
        with open(os.path.join(self.folder, "rns", "identity"), "rb") as f:
            self.assertEqual(f.read(), bytes(64))
        self.assertTrue(r["kept"] and os.path.isfile(r["kept"]), r)
        self.assertIn("isn't a saved Stump identity", T.team("restore", self.folder, home=self.home,
                                                            src=os.path.join(self.folder, "config.py"))["error"])


if __name__ == "__main__":
    sys.exit(0 if unittest.main(verbosity=1, exit=False).result.wasSuccessful() else 1)
