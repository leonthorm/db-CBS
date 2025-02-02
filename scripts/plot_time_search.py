import yaml
import matplotlib.pyplot as plt
import os
import numpy as np
# I - for the computation time plot
def read_yaml(file_path):
    # Read and parse the YAML file
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
    # time_nearestMotion 
    # time_hfun 
    try:
        return {
            "time_collision_heuristic": data['data']['time_collision_heuristic'],
            "time_collisions": data['data']['time_collisions'],
            "time_nearestNode": data['data']['time_nearestNode'],
            "time_rebuild_focal_set": data['data']['time_rebuild_focal_set'],
        }
    except KeyError as e:
        print(f"Error: Missing expected key {e} in the YAML data.")
        return None

def plot_stacked_bar(data_iterations, instances):
    instance_names = {
    "alcove_unicycle_sphere": "alcove",
    "gen_p10_n8_4_hetero": "hetero8",
    "drone4-C": "drone4-C",
    "drone4-R": "drone4-R",
    # "drone8-C": "drone8-C",
    # "drone8-R": "drone8-R",
    # "drone12-C": "drone12-C",
    # "drone12-R": "drone12-R",
     "wall8-C": "wall8-C",
     "wall8-R": "wall8-R",


    }

    # Data for plotting
    categories = {
        'Search-FH': 'time_collision_heuristic',
        'Search-Update FS': 'time_rebuild_focal_set',
        'Search-Collision': 'time_collisions',
        'Search-NN': 'time_nearestNode'
    }
    colors = ['skyblue', 'orange', 'grey', 'red']
    # labels = [f'Iteration {i + 1}' for i in range(len(data_iterations))] # to do: isntance name
    labels = list(instance_names.values())
    # Initialize plot
    fig, ax = plt.subplots()
    width = 0.4  # Bar width
    x_positions = range(len(data_iterations))  # Positions for each bar
    # Create stacked bars for each iteration
    for category_index, (category, key) in enumerate(categories.items()):
        bottoms = [sum(data[categories[c]] for c in list(categories.keys())[:category_index]) for data in data_iterations]
        values = [data[key] for data in data_iterations]
        ax.bar(x_positions, values, width, label=category, color=colors[category_index], bottom=bottoms)
    
    # Add legend, title, and labels
    ax.grid(which='both', axis='x', linestyle='dashed')
    ax.grid(which='major', axis='y', linestyle='dashed')
    ax.set_ylabel("Time [s]")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.legend(loc='upper left')
    plt.tight_layout()
    plt.grid(True)
    # Show the plot
    plt.show()

# File paths to your YAML files
path = "/home/akmarak-laptop/IMRC/db-CBS/results/tro-plots/time/"
instances = ["alcove_unicycle_sphere", "gen_p10_n8_4_hetero", "drone4-C", "drone4-R","wall8-C", "wall8-R" ] 

algorithms = [
    # "db-ecbs-residual",
    # "db-ecbs-conservative"
    "db-ecbs",
]
file_name = "time_search.yaml"
# List to store the combined paths
file_paths = []

# Generate paths by combining the base path, instance, and algorithm
for algo in algorithms:
    for instance in instances:
        file_paths.append(path + instance + "/" + algo + "/000/" + file_name)
# Read data from each YAML file
data_iterations = []
for file_path in file_paths:
    if os.path.exists(file_path):
        data = read_yaml(file_path)
        if data:
            data_iterations.append(data)

# plot_stacked_bar(data_iterations, instances)

def add_cost_and_time_over_robots_plot(a, i):
    folder = "/home/akmarak-laptop/IMRC/db-CBS/results/add_node/"
    t_values = {key: [] for key in a}  # Store t values for a1 and a2
    cost_values = {key: [] for key in a}  # Store t values for a1 and a2
    colors = ['red', 'blue']
    labels = ['Always Add', 'Rewire']
    x = np.array([1, 2, 3, 4]) 
    for a_instance in a:
        for i_instance in i:
            yaml_file = folder + a_instance + "/" + i_instance + "/db-ecbs/000/stats.yaml" 
            try:
                with open(yaml_file, 'r') as file:
                    data = yaml.safe_load(file)
                    stats = data["stats"]
                    if 'd_t' in data["stats"][0]:
                        t_values[a_instance].append(data["stats"][0]['d_t']) # always the only one stat
                        cost_values[a_instance].append(data["stats"][0]['d_cost']) # always the only one stat
                    else:
                        print(f"Warning: 't, cost' not found in {yaml_file}")
            except FileNotFoundError:
                print(f"Error: {yaml_file} not found")
                t_values[a_instance].append(None)  # Keep structure for plotting
                cost_values[a_instance].append(None)  # Keep structure for plotting
    fig, ax = plt.subplots(2, 1, sharex='all', sharey='none')
    for i in range(2):
    #   ax[i].set_xscale('log')
      ax[i].grid(which='both', axis='x', linestyle='dashed')
      ax[i].grid(which='major', axis='y', linestyle='dashed')

    parameters = {'p': cost_values, 't': t_values}
    for idx, (param, values) in enumerate(parameters.items()):
        for i in range(2):  # Two lines for each parameter
            ax[idx].plot(x, values[a[i]], color=colors[i], linewidth=3, alpha=0.8, label=labels[i])

    ax[0].legend()
    ax[0].set_ylabel(r"Cost [s]")
    ax[1].set_ylabel("Time [s]")
    ax[-1].set_xticks(x)
    i2 = [
        "drone2",
        "drone4",
        "drone8",
        "drone10",
    ]
    ax[-1].set_xticklabels(i2)
    plt.show()

def main():
    a = ["always_add", "rewire"]
    i = [
        "drone2c",
        "drone4c",
        "drone8c",
        "drone10c",
    ]
    add_cost_and_time_over_robots_plot(a, i)
    
if __name__ == "__main__":
  main()