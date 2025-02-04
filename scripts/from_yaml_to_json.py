import yaml
import json

def yaml_to_json(file_in, out_dir, N):
	
  with open(file_in, 'r') as file:
    data = yaml.safe_load(file)
  robot_data = [
    {"result": {"states": [], "actions": []}} for _ in range(N)
  ]
  
  for i in range(N): # polulu starts from 4
    # all_states = data['result'][i+N]['states'] 
    # states = [v[:2] + v[3:] for v in all_states]
    for i in range(N):  # Assuming 'polulu' starts at 4, ensure indexing is correct
      all_states = data['result'][i + N]['states']  # Check if this is valid
      robot_data[i]["result"]["states"] = [v[:2] + v[3:] for v in all_states]  # Store states correctly
      robot_data[i]["result"]["actions"] = data['result'][i + N]['actions']
    # actions = data['result'][i+N]['actions']
    # robot_data[i]["result"]["states"].append(states) 
    # robot_data[i]["result"]["actions"].append(actions) 

  for i in range(N): # polulu starts from 4
     output_path = f"{out_dir}/robot{i}.json"
     with open(output_path, 'w') as file:
        json.dump(robot_data[i], file, indent=4)

if __name__ == '__main__':
	yaml_in = "/home/akmarak-laptop/IMRC/db-CBS/results/demo/polulu-drone_hetero/test_opt2.yaml"
	out_dir = "/home/akmarak-laptop/IMRC/db-CBS/results/"
	yaml_to_json(yaml_in, out_dir, 4)