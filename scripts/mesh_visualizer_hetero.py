import numpy as np

# visualization related
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf
from meshcat.animation import Animation
from pathlib import Path

import argparse
import yaml
import time
import os
import matplotlib.pyplot as plt
def visualize(env_file, result_file):
    vis = meshcat.Visualizer()
    anim = Animation()

    res = vis.static_html()

    vis["/Cameras/default"].set_transform(
        tf.translation_matrix([0, 0, 0]).dot(
            tf.euler_matrix(0, np.radians(-30), np.radians(90))))
    
    vis["/Cameras/default/rotated/<object>"].set_transform(
        tf.translation_matrix([1, 0, 0]))


    with open(env_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        
    add_walls = False
    if(add_walls):
        # Define boundaries, my 3D problem
      min_bounds = np.array([-1.5, -1, 0])
      max_bounds = np.array([1.5, 1, 1])

      size = max_bounds - min_bounds
      floor_size = [size[0], size[1], 0.1]  # Thin floor
      wall_thickness = 0.1  # Thin walls

      # Add floor
      vis["floor"].set_object(g.Box(floor_size), g.MeshLambertMaterial(color=0x888888))
      vis["floor"].set_transform(
          meshcat.transformations.translation_matrix([(min_bounds[0] + max_bounds[0]) / 2,
                                                      (min_bounds[1] + max_bounds[1]) / 2,
                                                      min_bounds[2] - 0.05])  # Slightly below min z
      )

      # Add first wall (along x-axis)
      wall_x_size = [wall_thickness, size[1], size[2]]
      vis["wall_x"].set_object(g.Box(wall_x_size), g.MeshLambertMaterial(opacity=0.6, color=0xC0C0C0))
      vis["wall_x"].set_transform(
          meshcat.transformations.translation_matrix([min_bounds[0] - wall_thickness / 2,
                                                      (min_bounds[1] + max_bounds[1]) / 2,
                                                      min_bounds[2] + size[2] / 2])
      )

      # Add second wall (along y-axis)
      wall_y_size = [size[0], wall_thickness, size[2]]
      vis["wall_y"].set_object(g.Box(wall_y_size), g.MeshLambertMaterial(opacity=0.6, color=0xC0C0C0))
      vis["wall_y"].set_transform(
          meshcat.transformations.translation_matrix([(min_bounds[0] + max_bounds[0]) / 2,
                                                max_bounds[1] + wall_thickness / 2,
                                                min_bounds[2] + size[2] / 2])
      )

    with open(result_file) as res_file:
        result = yaml.load(res_file, Loader=yaml.FullLoader)
  
    states = []
    name_robot = 0
    max_k = 0
    polulu_size = [0.1, 0.1, 1.2]
    # start, goal states
    for i in range(len(result["result"])):
      state = []
      for s in result["result"][i]["states"]:
          state.append(s)

      max_k = max(max_k, len(state))
      states.append(state)

      # Extracting positions (assumes 3D)
      position = np.array([[sublist[j] for sublist in state] for j in range(3)])

      robot_type = data["robots"][i]["type"]

      # Visualization setup for each robot
      if robot_type == "integrator2_3d_v0":
          vis[f"Quadrotor{name_robot}"].set_object(
              g.StlMeshGeometry.from_file('../meshes/cf2_assembly.stl'),
              g.MeshLambertMaterial(color=0x0000FF)  # Blue
          )
      elif robot_type == "unicycle1_3d_v0":
          vis[f"Polulu{name_robot}"].set_object(
              g.Box(polulu_size),
              g.MeshLambertMaterial(color=0xFFA500)  # Orange
          )

      # Set trajectory visualization (Green)
      vis[f"trajectory{name_robot}"].set_object(
          g.Line(g.PointsGeometry(position), g.LineBasicMaterial(color=0x00FF00))
      )

      name_robot += 1

    # Animate both robots
    for k in range(max_k):
      for l in range(len(states)):  # Iterate over all robots
        with anim.at_frame(vis, 10 * k) as frame:
          robot_state = states[l][min(k, len(states[l]) - 1)]

          frame[f"Quadrotor{l}"].set_transform(
              tf.translation_matrix(robot_state[:3]).dot(
                  tf.quaternion_matrix(np.array([1, 0, 0, 0]))
              )
          )
          frame[f"Polulu{l}"].set_transform(
              tf.translation_matrix(robot_state[:3]).dot(
                  tf.quaternion_matrix(np.array([1, 0, 0, 0]))
              )
          )
          
      time.sleep(0.1)

    vis.set_animation(anim)
    res = vis.static_html()

    
    html_file = Path(result_file).with_suffix(".html")
    with open(html_file, "w") as f:
        f.write(res)

            
def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("env", help="input file containing map")
  parser.add_argument("--result", help="output file containing solution")
  args = parser.parse_args()

  visualize(args.env, args.result)

if __name__ == "__main__":
  main()
