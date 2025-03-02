import argparse
import subprocess
# import main_scp
# import main_komo
import tempfile
from pathlib import Path
import yaml

def run_ompl(filename_env, folder, timelimit, cfg):

	with tempfile.TemporaryDirectory() as tmpdirname:
		p = Path(tmpdirname)
		filename_cfg = p / "cfg.yaml"
		with open(filename_cfg, 'w') as f:
			yaml.dump(cfg, f, Dumper=yaml.CSafeDumper)
		
		with open("{}/log.txt".format(folder), 'w') as logfile: 
			result = subprocess.run(["./main_ompl", 
				"-i", filename_env,
				"-o", "{}/result_ompl.yaml".format(folder),
				"--stats", "{}/stats.yaml".format(folder),
				"--timelimit", str(timelimit),
				"-p", "sst",
				"-c", str(filename_cfg)],
				stdout=logfile, stderr=logfile)
		if result.returncode != 0:
			print("OMPL failed")

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("env", help="file containing the environment (YAML)")
	args = parser.parse_args()

	for i in range(1):
		run_ompl(args.env, i)


if __name__ == '__main__':
	main()
