"""Run every (arm, fold, seed) training job, two at a time, one CPU thread each; skips finished jobs.

    python ml_driver.py <arms> [seeds] ["extra arguments for hinigram_resonet.py"]
An arm written "lin_sync-e80" runs lin_sync with --suffix -e80; give its schedule in the extra arguments, e.g.
    python ml_driver.py lin_sync-e80 0,1 "--epochs 80 --patience 15"
"""
import itertools
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
arms = sys.argv[1].split(",")
seeds = [int(s) for s in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["0"])]
extra = sys.argv[3].split() if len(sys.argv) > 3 else []
workers = int(os.environ.get("HINIGRAM_WORKERS", "2"))
out = os.path.join(HERE, "mlruns")
os.makedirs(out, exist_ok=True)
env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
           XLA_FLAGS="--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1")
jobs = [(a, f, s) for s, a, f in itertools.product(seeds, arms, range(3))
        if not os.path.exists(os.path.join(out, f"{a}_f{f}_s{s}_summary.json"))]   # arm "x-p0" = arm x without pooling
print(len(jobs), "jobs", flush=True)
running, t0 = [], time.time()
while jobs or running:
    while jobs and len(running) < workers:
        a, f, s = jobs.pop(0)
        log = open(os.path.join(out, f"{a}_f{f}_s{s}.stdout"), "w")
        base, pool = (a[:-3], "0") if a.endswith("-p0") else (a, "1")
        base, suffix = (base.split("-", 1)[0], "-" + base.split("-", 1)[1]) if "-" in base else (base, "")   # "lin_sync-e80" -> lin_sync, -e80
        running.append(((a, f, s), subprocess.Popen([sys.executable, os.path.join(HERE, "hinigram_resonet.py"), "--arm", base, "--fold", str(f),
                                                      "--seed", str(s), "--pool", pool] + ([f"--suffix={suffix}"] if suffix else []) + extra,
                                                     stdout=log, stderr=subprocess.STDOUT, env=env, cwd=HERE)))
    time.sleep(5)
    for job, p in list(running):
        if p.poll() is not None:
            running.remove((job, p))
            print(f"{job} exit {p.returncode} at {time.time() - t0:.0f}s", flush=True)
print("all done", f"{time.time() - t0:.0f}s", flush=True)
