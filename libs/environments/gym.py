"""
OpenAI Gym Environments
"""

import time
import numpy as np
import gym
import gym.spaces
from skimage.color import rgb2gray
import cv2
from libs.discretize import create_uniform_grid
from libs.visualize import show_frames_2d, show_frames_3d, show_frame


class Gym():
    """
    Basic Gym environment.  Works with a lot of the more simple environments like:
    CartPole, MountainCar, LunarLander, FrozenLake, etc.
    """

    def __init__(self, name, seed, max_steps=None, one_hot=None, action_bins=None, normalize=False):
        """
        Params
        ======
            name (str): Environment name
            seed (int): Random seed
            max_steps (int): Maximum number of steps to run before returning done
            one_hot (int): Size of 1-D one-hot vector
            action_bins (tuple): Number of splits to divide each dimension of continuous space
            normalize (bool): Whether to normalize the state input
        """
        self.seed = seed
        print('SEED: {}'.format(self.seed))
        self.one_hot = one_hot
        self.action_bins = action_bins
        self.normalize = normalize
        self.env = gym.make(name)
        self.env = gym.wrappers.Monitor(self.env, "recording")  # uncomment to record video
        self.env.seed(seed)
        if max_steps:  # override environment default for max steps in an episode
            self.env._max_episode_steps = max_steps
        if normalize:  # grab value to use for normalization
            self.obs_space_high = self.env.observation_space.high[0]
        self.frame_sleep = 0.02

    def reset(self):
        """Reset the environment."""
        state = self.env.reset()
        if self.one_hot:
            state = np.eye(self.one_hot)[state]
        if self.normalize:  # normalize state input (used in atari ram environments).  DEPRECATED?
            state = state / self.obs_space_high
        return state

    def step(self, action):
        """Take a step in the environment."""
        # convert discrete output from model to continuous action space
        if self.action_bins:
            action_grid = create_uniform_grid(self.env.action_space.low,
                                              self.env.action_space.high,
                                              bins=self.action_bins)
            state, reward, done, _ = self.env.step([action_grid[0][action]])
        else:
            state, reward, done, _ = self.env.step(action)
        if self.one_hot:  # needed when each state is represented as an integer, e.g. FrozenLake
            state = np.eye(self.one_hot)[state]
        if self.normalize:  # normalize state input (used in atari ram environments).  DEPRECATED?
            state = state / self.obs_space_high
        return state, reward, done

    def render(self):
        """Render the environment to visualize the agent interacting."""
        self.env.render()
        time.sleep(self.frame_sleep)


class GymAtari(Gym):
    """
    OpenAI Gym Environment for use with Atari games.
    Does pre-processing generic to most Atari games.
    Stacks 4 frames into state.
    """

    def __init__(self, name, seed):
        super(GymAtari, self).__init__(name, seed)
        self.full_state = np.zeros((1, 4, 80, 80), dtype=np.float32)

    def _prepro(self, frame):
        """Pre-process 210x160x3 uint8 frame into 80x80 float32 frame."""
        frame = rgb2gray(frame)  # convert to grayscale
        #print('_prepro() frame after rgb2gray:  {}'.format(frame))  # DEBUG
        frame = cv2.resize(frame, (80, 80), interpolation=cv2.INTER_AREA)  # downsample
        #print('_prepro() frame after resize:  {}'.format(frame))  # DEBUG
        return frame

    def _add_frame(self, frame):
        """ Add single frame to state.  Used for processing multiple states over time."""
        self.full_state[:, 3, :, : :] = self.full_state[:, 2, :, : :]
        self.full_state[:, 2, :, : :] = self.full_state[:, 1, :, : :]
        self.full_state[:, 1, :, : :] = self.full_state[:, 0, :, : :]
        self.full_state[:, 0, :, : :] = frame

    def reset(self):
        """Reset the environment."""
        frame = self.env.reset()
        #print('reset() frame from environment:  {}'.format(frame.shape))  # DEBUG
        frame = self._prepro(frame)
        #print('reset() frame after _prepro():  {}'.format(frame.shape))  # DEBUG
        frame = frame.reshape(1, 80, 80)
        #print('reset() frame after reshape:  {}'.format(frame.shape))  # DEBUG
        self._add_frame(frame)
        self._add_frame(frame)
        self._add_frame(frame)
        self._add_frame(frame)
        #print('reset():  {}'.format(self.full_state.shape))  # DEBUG
        return self.full_state.copy()

    def step(self, action):
        """Take a step in the environment.  Given an action, return the next state."""
        frame, reward, done, _ = self.env.step(action)
        #print('step() frame from environment:  {}'.format(frame.shape))  # DEBUG
        frame = self._prepro(frame)
        #print('step() frame after _prepro():  {}'.format(frame.shape))  # DEBUG
        frame = frame.reshape(1, 80, 80)
        #print('step() frame after reshape:  {}'.format(frame.shape))  # DEBUG
        self._add_frame(frame)
        #print('step():  {}'.format(self.full_state.shape))  # DEBUG
        return self.full_state.copy(), reward, done



class GymAtariPong(GymAtari):
    """
    OpenAI Gym Environment for use only with Pong.
    Does pre-processing specific to Pong game.
    """

    # this function is from https://gist.github.com/karpathy/a4166c7fe253700972fcbc77e4ea32c5
    def _prepro(self, frame):
        """ Pre-process 210x160x3 uint8 frame into 80x80 uint8 frame.
            Custom pre-processing that only works with Pong.
            Maybe is cheating a bit but definitely speeds up learning.
        """
        frame = frame[35:195] # crop
        frame = frame[::2, ::2, 0] # downsample by factor of 2
        frame[frame == 144] = 0 # erase background (background type 1)
        frame[frame == 109] = 0 # erase background (background type 2)
        frame[frame != 0] = 1 # everything else (paddles, ball) just set to 1
        return frame