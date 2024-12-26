import numpy as np
import yaml
from pathlib import Path
import argparse
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf
from meshcat.animation import Animation

DnametoColor = {
    "red": 0xff0000,
    "green": 0x00ff00,
    "blue": 0x0000ff,
    "yellow": 0xffff00,
    "white": 0xffffff,
    "black": 0x000000,
    "cyan": 0x00ffff,
    "magenta": 0xff00ff,
    "orange": 0xffa500,
    "purple": 0x800080
}

def visualize(env_file, result_file, video_file, reference_traj):
    vis = meshcat.Visualizer()
    anim = Animation()

    # Load environment
    with open(env_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    obstacles = data["environment"]["obstacles"]
    for k, obs in enumerate(obstacles):
        center = obs["center"]
        size = obs["size"]
        vis[f"Obstacle_Box{k}"].set_object(g.Mesh(g.Box(size)))
        vis[f"Obstacle_Box{k}"].set_transform(tf.translation_matrix(center))

    # Load result states
    with open(result_file) as res_file:
        result = yaml.load(res_file, Loader=yaml.FullLoader)

    # result = result["result"]
    # states = result["states"]
    if "states" in result and "actions" in result:
        result = result
    else:
        result = result["result"]
    if isinstance(result, list):
        states = result[0]["states"]
    else:
        states = result["states"]

    # num_robots = len(states[0]) - len(obstacles) - 2  # Adjusted state size
    num_robots = data["robots"][0]["quadsNum"]
    # Visualize robots and rods
    for i in range(num_robots):
        vis[f"unicycle{i}"].set_object(g.Mesh(g.Box([0.1, 0.05, 0.05]), material=g.MeshLambertMaterial(color=list(DnametoColor.items())[i][1])))
    for i in range(num_robots - 1):
        vis[f"cable{i}"].set_object(g.Mesh(g.Box([0.5, 0.01, 0.01]), material=g.MeshLambertMaterial(color="black")))

    for k, state in enumerate(states):
        with anim.at_frame(vis, k) as frame:
            px1, py1, alpha1 = state[0], state[1], state[2]
            # exit()
            frame[f"unicycle0"].set_transform(
                tf.translation_matrix([px1, py1, 0]).dot(
                    tf.quaternion_matrix(tf.quaternion_from_euler(0, 0, alpha1))
                )
            )
            l = 0.5
            px_prev = px1
            py_prev = py1
            for i in range(num_robots-1):
                alpha    = state[2 + i + 1]
                th_cable = state[2 + num_robots + i]
                px_prev = px_prev + l*np.cos(th_cable)
                py_prev = py_prev + l*np.sin(th_cable)
                # print("px py alpha", alpha)
                frame[f"unicycle{i+1}"].set_transform(
                    tf.translation_matrix([px_prev, py_prev, 0]).dot(
                        tf.quaternion_matrix(tf.quaternion_from_euler(0, 0, alpha))
                    )
                )
            px_prev = px1
            py_prev = py1
            for i in range(num_robots - 1):
                th_cable = state[2 + num_robots + i]
                px_prev_cable = px_prev + 0.5*l*np.cos(th_cable)
                py_prev_cable = py_prev + 0.5*l*np.sin(th_cable)
                px_prev = px_prev + l*np.cos(th_cable)
                py_prev = py_prev + l*np.sin(th_cable)

                # print("th_cable: ",th_cable)
                frame[f"cable{i}"].set_transform(
                    tf.translation_matrix([px_prev_cable, py_prev_cable, 0]).dot(
                        tf.quaternion_matrix(tf.quaternion_from_euler(0, 0, th_cable))
                    )
                )
            # exit()
    vis.set_animation(anim)
    res = vis.static_html()
    with open(video_file, "w") as f:
        f.write(res)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--robot', type=str, help="robot model: unicycle")
    parser.add_argument('--env', type=str, help="environment")
    parser.add_argument('--ref', type=str, help="reference trajectory")
    parser.add_argument('--result', type=str, help="result trajectory")
    parser.add_argument('--output', type=str, help="html animation")
    parser.add_argument("-i", "--interactive", action="store_true")  # on/off flag

    args = parser.parse_args()
    visualize(args.env, args.result, args.output, args.ref)


if __name__ == "__main__":
    main()
