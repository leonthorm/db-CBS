#!/usr/bin/env python3
import argparse
import numpy as np
import yaml
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.patches import Circle, Circle, Arrow, Rectangle
from matplotlib import animation
import matplotlib.animation as manimation
import os
import sys
from iteration_utilities import deepflatten
import subprocess

def draw_sphere_patch(ax, center, radius, angle = 0, **kwargs):
  xy = np.asarray(center) 
  sphere = Circle(xy, radius, **kwargs)
  t = matplotlib.transforms.Affine2D().rotate_around(
      center[0], center[1], angle)
  sphere.set_transform(t + ax.transData)
  ax.add_patch(sphere)
  return sphere

def draw_box_patch(ax, center, size, angle = 0, **kwargs):
  xy = np.asarray(center) - np.asarray(size) / 2
  rect = Rectangle(xy, size[0], size[1], **kwargs)
  t = matplotlib.transforms.Affine2D().rotate_around(
      center[0], center[1], angle)
  rect.set_transform(t + ax.transData)
  ax.add_patch(rect)
  return rect


class Animation:
  def __init__(self, filename_env, filename_result = None, filename_output = None):
    with open(filename_env) as env_file:
      env = yaml.safe_load(env_file)

    self.fig = plt.figure() 
    self.ax = self.fig.add_subplot(111, aspect='equal')
    self.ax.set_xlim(env["environment"]["min"][0], env["environment"]["max"][0])
    self.ax.set_ylim(env["environment"]["min"][1], env["environment"]["max"][1])
    self.robot_numbers = len(env["robots"])
    self.size = np.array([0.5, 0.25])
    self.trailer_size = np.array([0.3, 0.25])
    self.hitch_length = [0.5]
    self.radius = 0.1
    self.big_radius = 0.40
    self.robot_types = []

    for obstacle in env["environment"]["obstacles"]:
      if obstacle["type"] == "box":
        draw_box_patch(
            self.ax, obstacle["center"], obstacle["size"], facecolor='gray', edgecolor='black')
      else:
        print("ERROR: unknown obstacle type")

    cmap = matplotlib.cm.get_cmap('jet')

    self.colors = cmap(np.linspace(0, 1, len(env["robots"]), True))

    for robot, color in zip(env["robots"], self.colors):
      self.robot_types.append(robot["type"])  
      if filename_result is None:
        self.draw_robot(robot["start"], robot["type"], facecolor=color, alpha=0.3)
      if filename_output is None:
        self.draw_robot(robot["goal"], robot["type"], facecolor='none', edgecolor=color, alpha=0.3)

    if filename_result is not None:
      with open(filename_result) as result_file:
        self.result = yaml.safe_load(result_file)

      # draw trajectory
      for robot, robot_type, color in zip(self.result["result"], self.robot_types, self.colors):
        self.draw_trajectory(robot["states"], robot_type, color=color, alpha=0.5)

      T = 0
      for robot in self.result["result"]:
        T = max(T, len(robot["states"]))
      print("T", T)

      if filename_output is not None:
        from pathlib import Path

        add_patches = []
        for robot, robot_type, color in zip(self.result["result"], self.robot_types, self.colors):
          for t in np.arange(0, T+21, 20):
            if t >= len(robot["states"]):
              state = robot["states"][-1]
            else:
              state = robot["states"][t]
            print(t, state, len(robot["states"]))
            add_patches.extend(self.draw_robot(state, robot_type, facecolor=color, alpha=0.2+0.6*min(t,len(robot["states"]))/T))
            if t >= len(robot["states"]):
              break
        fname = str(Path(filename_output).with_suffix(".pdf"))
        self.ax.get_xaxis().set_visible(False)
        self.ax.get_yaxis().set_visible(False)
        self.fig.savefig(fname)
        subprocess.run(["pdfcrop", fname, fname])
        for p in add_patches:
          p.remove()
        self.ax.get_xaxis().set_visible(True)
        self.ax.get_yaxis().set_visible(True)

      self.robot_patches = []
      i = 0
      for robot, color in zip(self.result["result"], self.colors):
        state = robot["states"][0]
        patches = self.draw_robot(state, self.robot_types[i], facecolor=color, alpha=0.8)
        self.robot_patches.append(patches)
        i += 1
      self.anim = animation.FuncAnimation(self.fig, self.animate_func,
                                frames=T,
                                interval=100,
                                blit=True)

  def save(self, file_name, speed):
    self.anim.save(
      file_name,
      "ffmpeg",
      fps=10 * speed,
      dpi=200),
      # savefig_kwargs={"pad_inches": 0, "bbox_inches": "tight"})

  def show(self):
    plt.show()

  def animate_func(self, i):
    print(i)
    for k, robot in enumerate(self.result["result"]): # for each robot
      if i >= len(robot["states"]):
        state = robot["states"][-1]
      else:
        state = robot["states"][i]
        if self.robot_types[k] == 'single_integrator_0':
            pos = state
            xy = np.asarray(pos)
            self.robot_patches[k][0].center = xy
            t = matplotlib.transforms.Affine2D().rotate_around(
                pos[0], pos[1], 0)
            self.robot_patches[k][0].set_transform(t + self.ax.transData)
        elif self.robot_types[k] == 'double_integrator_0':
            pos = state[:2]
            xy = np.asarray(pos)
            self.robot_patches[k][0].center = xy
            t = matplotlib.transforms.Affine2D().rotate_around(
                pos[0], pos[1], 0)
            self.robot_patches[k][0].set_transform(t + self.ax.transData)
        elif self.robot_types[k] == 'unicycle_first_order_0_sphere':
            pos = state[:2]
            yaw = state[2]
            xy = np.asarray(pos)
            self.robot_patches[k][0].center = xy
            pos2 = xy + np.array([np.cos(yaw), np.sin(yaw)])*self.big_radius*0.8
            self.robot_patches[k][1].center = pos2
        elif self.robot_types[k] == 'unicycle_first_order_0' or self.robot_types[k] == 'car_first_order_0' or self.robot_types[k] == 'unicycle_second_order_0':
            pos = state[:2]
            yaw = state[2]
            xy = np.asarray(pos) - np.asarray(self.size) / 2
            self.robot_patches[k][0].set_xy(xy)
            t = matplotlib.transforms.Affine2D().rotate_around(
                pos[0], pos[1], yaw)
            self.robot_patches[k][0].set_transform(t + self.ax.transData)
            pos2 = pos + np.array([np.cos(yaw), np.sin(yaw)])*self.size[0]/2*0.8
            self.robot_patches[k][1].center = pos2
        elif self.robot_types[k] == "car_first_order_with_1_trailers_0":
            pos0 = state[0:2]
            theta0 = state[2]
            theta1 = state[3]
            pos1 = pos0 - np.array([np.cos(theta1), np.sin(theta1)]
                                  ) * self.hitch_length[0]

            xy = np.asarray(pos0) - np.asarray(self.size) / 2
            self.robot_patches[k][0].set_xy(xy)
            t = matplotlib.transforms.Affine2D().rotate_around(
                pos0[0], pos0[1], theta0)
            self.robot_patches[k][0].set_transform(t + self.ax.transData)

            xy = np.asarray(pos1) - np.asarray(self.trailer_size) / 2
            self.robot_patches[k][1].set_xy(xy)
            t = matplotlib.transforms.Affine2D().rotate_around(
                pos1[0], pos1[1], theta1)
            self.robot_patches[k][1].set_transform(t + self.ax.transData)

            pos2 = pos0 + np.array([np.cos(theta0), np.sin(theta0)])*self.size[0]/2*0.8
            self.robot_patches[k][2].center = pos2

    return [item for row in self.robot_patches for item in row]

  def draw_robot(self, state, type, **kwargs):
    patches = []
    if type == 'single_integrator_0':
      pos = state
      patches.append(draw_sphere_patch(self.ax, state, self.radius, 0, **kwargs))
    elif type == 'double_integrator_0':
        pos = state[:2]
        patches.append(draw_sphere_patch(self.ax, state, self.radius, 0, **kwargs))
    elif type == 'unicycle_first_order_0_sphere':
        pos = state[:2]
        yaw = state[2]
        pos2 = pos + np.array([np.cos(yaw), np.sin(yaw)])*self.big_radius*0.8
        patches.append(draw_sphere_patch(self.ax, pos, self.big_radius, 0, **kwargs))
        kwargs['facecolor'] = 'black'
        patches.append(draw_sphere_patch(self.ax, pos2, 0.03, 0, **kwargs))
    elif type == 'unicycle_first_order_0' or type == 'car_first_order_0' or type == 'unicycle_second_order_0':
        pos = state[:2]
        yaw = state[2]
        pos2 = pos + np.array([np.cos(yaw), np.sin(yaw)])*self.size[0]/2*0.8
        if type == 'unicycle_second_order_0':
          kwargs['hatch'] =r"//"
          kwargs['edgecolor'] = kwargs["facecolor"]
        else:
          kwargs['hatch'] = None
          kwargs['edgecolor'] = None
        patches.append(draw_box_patch(self.ax, pos, self.size, yaw, **kwargs))
        kwargs['facecolor'] = 'black'
        patches.append(draw_sphere_patch(self.ax, pos2, 0.03, 0, **kwargs))
    elif type == "car_first_order_with_1_trailers_0":
        pos = state[0:2]
        theta0 = state[2]
        theta1 = state[3]
        patches.append(draw_box_patch(self.ax, pos, self.size, theta0, **kwargs))
        link1 = np.array([np.cos(theta1), np.sin(theta1)]) * self.hitch_length[0]
        patches.append(draw_box_patch(self.ax, pos-link1, self.trailer_size, theta1, **kwargs))
        pos2 = pos + np.array([np.cos(theta0), np.sin(theta0)])*self.size[0]/2*0.8
        kwargs['facecolor'] = 'black'
        patches.append(draw_sphere_patch(self.ax, pos2, 0.03, 0, **kwargs))
    return patches
  
  def draw_trajectory(self, states, type, color, **kwargs):
    states = np.array(states)
    if color is not None:
      self.ax.plot(states[:,0], states[:,1], color=color, **kwargs)
    else:

      # self.ax.scatter(states[:,0], states[:,1],c=range(len(states)), marker='o',s=5)
      from matplotlib.collections import LineCollection

      points = states[:,0:2].reshape(-1, 1, 2)
      # print(points.shape)
      # x    = np.linspace(0,1, 100)
      # y    = np.linspace(0,1, 100)
      # cols = np.linspace(0,1,len(x))
      # points = np.array([x, y]).T.reshape(-1, 1, 2)
      # print(points.shape)
      # exit()

      segments = np.concatenate([points[:-1], points[1:]], axis=1)
      cols = np.linspace(0,1,len(points))

      lc = LineCollection(segments, cmap='viridis', zorder=1)
      lc.set_array(cols)
      lc.set_linewidth(5)
      line = self.ax.add_collection(lc)
      # fig.colorbar(line,ax=ax)



def visualize(filename_env, filename_result = None, filename_video=None):
  anim = Animation(filename_env, filename_result, filename_video)
  # anim.save(filename_video, 1)
  # anim.show()
  if filename_video is not None:
    anim.save(filename_video, 1)
  else:
    anim.show()

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("env", help="input file containing map")
  parser.add_argument("--result", help="output file containing solution")
  parser.add_argument("--video", help="output file for video")
  args = parser.parse_args()

  visualize(args.env, args.result, args.video)

if __name__ == "__main__":
  main()
