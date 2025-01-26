import yaml
import matplotlib.pyplot as plt

import yaml
import matplotlib.pyplot as plt

def read_yaml(file_path):
    # Read and parse the YAML file
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
    
    try:
        return {
            "time_collision_heuristic": data['data']['time_collision_heuristic'],
            "time_collisions": data['data']['time_collisions'],
            "time_nearestNode": data['data']['time_nearestNode']
        }
    except KeyError as e:
        print(f"Error: Missing expected key {e} in the YAML data.")
        return None

def plot_stacked_bar(data_iterations):
    # Data for plotting
    categories = {
        'Collision Heuristic': 'time_collision_heuristic',
        'Collisions': 'time_collisions',
        'Nearest Node': 'time_nearestNode'
    }
    colors = ['skyblue', 'orange', 'green']
    labels = [f'Iteration {i + 1}' for i in range(len(data_iterations))]
    
    # Initialize plot
    fig, ax = plt.subplots()
    width = 0.2  # Bar width
    x_positions = range(len(data_iterations))  # Positions for each bar
    
    # Create stacked bars for each iteration
    for category_index, (category, key) in enumerate(categories.items()):
        bottoms = [sum(data[categories[c]] for c in list(categories.keys())[:category_index]) for data in data_iterations]
        values = [data[key] for data in data_iterations]
        ax.bar(x_positions, values, width, label=category, color=colors[category_index], bottom=bottoms)
    
    # Add legend, title, and labels
    ax.set_title("Time Breakdown Across Iterations")
    ax.set_ylabel("Time (seconds)")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.legend(title="Categories")
    plt.tight_layout()
    
    # Show the plot
    plt.show()

# File paths to your YAML files
path = "/home/akmarak-laptop/IMRC/db-CBS/results/"
instance = "drone2c"
algorithms = [
    "db-ecbs-residual",
    "db-ecbs-conservative"
]
file_name = "time_search.yaml"
# List to store the combined paths
file_paths = []

# Generate paths by combining the base path, instance, and algorithm
for algo in algorithms:
    file_paths.append(path + instance + "/" + algo + "/000/" + file_name)

# Read data from each YAML file
data_iterations = []
for file_path in file_paths:
    data = read_yaml(file_path)
    if data:
        data_iterations.append(data)

# Plot the data if both iterations were successfully read
if len(data_iterations) == len(file_paths):
    plot_stacked_bar(data_iterations)
