import yaml
import json

def yaml_to_json(file_in, out_dir, N):
	
  with open(file_in, 'r') as file:
    data = yaml.safe_load(file)

  robot_data = [
    {"result": {"states": [], "actions": []}} for _ in range(N)
  ]
  
  for i in range(N):
    states = data['result'][i]['states'] 
    actions = data['result'][i]['actions']
    robot_data[i]["result"]["states"].append(states) 
    robot_data[i]["result"]["actions"].append(actions) 

  for i in range(N):
     output_path = f"{out_dir}/robot{i}.json"
     with open(output_path, 'w') as file:
        json.dump(robot_data[i], file, indent=4)

if __name__ == '__main__':
	yaml_in = "/home/akmarak-laptop/IMRC/db-CBS/results/demo/polulu_opt.yaml"
	out_dir = "/home/akmarak-laptop/IMRC/db-CBS/results/demo"
	yaml_to_json(yaml_in, out_dir, 1)