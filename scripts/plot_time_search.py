import yaml
import matplotlib.pyplot as plt
import os

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
    # ax.set_title("Time Breakdown Across Iterations")
    ax.set_ylabel("Time [s]")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    # ax.legend(loc='upper left',bbox_to_anchor=(1, 1))
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
# Plot the data if both iterations were successfully read
# if len(data_iterations) == len(file_paths):
plot_stacked_bar(data_iterations, instances)
