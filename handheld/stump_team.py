#!/usr/bin/env python3
"""The handheld Stump's packs, identity and announce stamps, by Team Stump's
own code: its SandBox_Stump_On clone's provisioner.py, the functions behind
`--packs FOLDER`, `--save-identity`, `--restore-identity` and
`--stamp-announces` (1.0.0-beta.75, .76, .86). The cockpit's OWNER tab
calls these; they ask nothing.

Each call runs the Stump's own Python (its venv) on a small script that
imports provisioner.py, given one JSON line on stdin, and reads back one
line (TEAM{...}). What provisioner.py prints along the way is kept apart.

The same on dArkOS / arkos4clone and on RK3326 Linux: ~/Stump and
~/SandBox_Stump_On are where R36MAX-Stump's installer puts them on both.
Identity files are kept on RK3326 Linux's data partition (/data/ark, which
survives a reflash) when it's there, else in the home folder: never on the
games card (exFAT keeps no file permissions, and the file is the Stump's
keys).
"""
import glob
import json
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
KEEPSAKE_EXT = ".stump-identity"

TEAM_CODE = r"""
import importlib.util, io, json, os, sys, time
job = json.loads(sys.stdin.readline())
out = {}
real = sys.stdout
sys.stdout = io.StringIO()                       # what it prints along the way: kept apart
try:
    spec = importlib.util.spec_from_file_location("team_stump", os.path.join(job["clone"], "provisioner.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)
    folder, do = job["folder"], job["do"]
    if do in ("packs", "install", "remove") and not hasattr(P, "pc_install_pack"):
        out = {"old": "1.0.0-beta.75"}
    elif do in ("save", "restore") and not hasattr(P, "read_identity_source"):
        out = {"old": "1.0.0-beta.76"}
    elif do == "stamps" and not hasattr(P, "stamp_announces"):
        out = {"old": "1.0.0-beta.86"}
    elif do == "stamps":
        wanted, have = P._stamps_files(folder)[2:]
        todo = sum(1 for h, m in wanted.items() if not P._stamp_ok(bytes.fromhex(m), bytes.fromhex(have.get(h, ""))))
        out = {"total": len(wanted), "todo": todo, "ok": bool(wanted) and bool(P.stamp_announces(folder))}
    elif do in ("packs", "install", "remove"):
        avail = P.discover_packs()
        rows = P.pack_rows(avail, P.pc_installed_packs(folder))
        if do == "install":
            pk = next((p for p in avail if p["spec"]["name"] == job["name"]), None)
            out = {"ok": bool(pk) and bool(P.pc_install_pack(folder, pk))}
        elif do == "remove":
            r = next((r for r in rows if r["name"] == job["name"] and r["here"] is not None), None)
            out = {"ok": bool(r) and bool(P.pc_remove_pack(folder, r, bool(job.get("also"))))}
        if do != "packs":
            rows = P.pack_rows(avail, P.pc_installed_packs(folder))
        res = []
        for r in rows:
            data, tools, home, theme = P._pack_leftovers(r, board=False)
            spec_ = r["pack"]["spec"] if r["pack"] else {}
            res.append({"name": r["name"], "here": r["here"], "state": r["state"], "plugins": r["plugins"],
                        "version": str(spec_.get("version", "")) if r["pack"] else None,
                        "about": str(spec_.get("description") or ""),
                        "keeps": {"tools": len(tools), "home": len(home), "theme": theme}})
        out["rows"] = res
    elif do == "save":
        files = P.pc_identity(folder)
        if not files:
            out = {"error": "No identity there yet: a Stump makes it the first time it starts."}
        else:
            name = P._folder_name(folder)
            path = os.path.join(job["dir"], P._keepsake_name(name))
            base, k = path[:-len(P.KEEPSAKE_EXT)], 2
            while os.path.exists(path):
                path, k = "%s (%d)%s" % (base, k, P.KEEPSAKE_EXT), k + 1
            out = {"path": str(P.save_keepsake(files, name, path)), "fingerprint": P.identity_fingerprint(files)}
    elif do == "restore":
        try:
            files, name = P.read_identity_source(job["src"])
        except ValueError as e:
            out = {"error": str(e)}
        else:
            cur, here, kept = P.pc_identity(folder), P._folder_name(folder), None
            if cur and cur != files:                 # kept first, under a name never used before
                path = os.path.join(job["keep"], P._keepsake_name(
                    "%s (replaced %s)" % (here or "Stump", time.strftime("%Y-%m-%d %H%M"))))
                base, k = path[:-len(P.KEEPSAKE_EXT)], 2
                while os.path.exists(path):
                    path, k = "%s (%d)%s" % (base, k, P.KEEPSAKE_EXT), k + 1
                kept = P.save_keepsake(cur, here, path)
            P.pc_put_identity(folder, files)
            out = {"name": name, "fingerprint": P.identity_fingerprint(files), "kept": str(kept) if kept else None}
    else:
        out = {"error": "unknown"}
except Exception as e:
    out = {"error": "%s: %s" % (type(e).__name__, e)}
sys.stdout = real
print("TEAM" + json.dumps(out))
"""


def python_for(folder):
    """The Stump's own Python (its venv: everything provisioner.py imports), else this one."""
    py = os.path.join(folder, "venv", "bin", "python")
    return py if os.path.isfile(py) else (sys.executable or "python3")


def team(do, folder, home=None, run=subprocess.run, timeout=300, **job):
    """Calls Team Stump's provisioner.py for this handheld's Stump. Its
    answer: a dict; {"error"} when it couldn't, {"old": release} when the
    clone is older than what this needs."""
    home = home or HOME
    clone = os.environ.get("SANDBOX_DIR") or os.path.join(home, "SandBox_Stump_On")
    if not os.path.isfile(os.path.join(clone, "provisioner.py")):
        return {"error": "No SandBox_Stump_On next to it (run its install again)"}
    job.update(clone=clone, folder=folder, do=do)
    try:
        p = run([python_for(folder), "-I", "-c", TEAM_CODE], input=json.dumps(job) + "\n", cwd=home,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}
    m = re.search(r"^TEAM(\{.*\})$", p.stdout or "", re.M)
    if not m:
        return {"error": ((p.stdout or "").strip().splitlines() or ["no answer"])[-1][-200:]}
    try:
        return json.loads(m.group(1))
    except ValueError:
        return {"error": "an answer that won't read"}


def keeps_text(row):
    """What a pack leaves behind when removed, in words."""
    k = row.get("keeps") or {}
    out = ["its saved data"]
    if k.get("tools"):
        out.append("its Tools page section%s" % ("s" if k["tools"] > 1 else ""))
    if k.get("home"):
        out.append("%d home file%s" % (k["home"], "s" if k["home"] > 1 else ""))
    if k.get("theme"):
        out.append("its theme (%s)" % k["theme"])
    return ", ".join(out)


def keep_dir(data="/data/ark", home=None):
    """Where a saved identity goes: RK3326 Linux's data partition, else home."""
    if os.path.isdir(data) and os.access(data, os.W_OK):
        return data
    return home or HOME


def keepsakes(dirs=None, home=None):
    """Saved identities to bring back: [path], newest first, from the data
    partition, the home folder and the games card (one copied there by
    card reader)."""
    home = home or HOME
    dirs = dirs or ["/data/ark", home, "/roms", "/roms2", os.path.join(home, "Stump")]
    found, seen = [], set()
    for d in dirs:
        for p in glob.glob(os.path.join(d, "*" + KEEPSAKE_EXT)):
            real = os.path.realpath(p)
            if real not in seen and os.path.isfile(p):
                seen.add(real)
                found.append(p)
    return sorted(found, key=lambda p: -os.path.getmtime(p))
