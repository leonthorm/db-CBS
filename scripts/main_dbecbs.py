import subprocess
import time
import tempfile
from pathlib import Path
import sys
import os
import yaml

sys.path.append(os.getcwd())


def run_dbecbs(filename_env, folder, timelimit, cfg):
    with tempfile.TemporaryDirectory() as tmpdirname:
        p = Path(tmpdirname)
        filename_cfg = p / "cfg.yaml"
        with open(filename_cfg, 'w') as f:
            yaml.dump(cfg, f, Dumper=yaml.CSafeDumper)

        print(filename_env)
        filename_stats = "{}/stats.yaml".format(folder)
        with open(filename_stats, 'w') as stats:
            stats.write("stats:\n")
            
            filename_result_dbecbs = Path(folder) / "result_dbecbs.yaml"
            filename_result_dbecbs_opt = Path(folder) / "result_dbecbs_opt.yaml"
            filename_stats = Path(folder) / "stats.yaml"

            cmd = ["./db_ecbs", 
                "-i", filename_env,
                "-o", filename_result_dbecbs,
                "--opt", filename_result_dbecbs_opt,
                "--stats", filename_stats,
                "--cfg", str(filename_cfg),
                "-t", str(1e6)]
            print(subprocess.list2cmdline(cmd))
            try:
                with open("{}/log.txt".format(folder), 'w') as logfile:
                    result = subprocess.run(cmd, timeout=timelimit, stdout=logfile, stderr=logfile) # no use
                    if(result.returncode != 0 or result.returncode == 0):
                        if Path(filename_result_dbecbs_opt).exists():
                            print("db-ecbs success!")
                        else: 
                            print("db-ecbs fail!")
            except:
                print("Failure!")



