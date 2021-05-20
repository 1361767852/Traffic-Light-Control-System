from __future__ import absolute_import
from __future__ import print_function

import traci
import numpy as np
import random
import timeit
from Simulation import Simulation

import os
from shutil import copyfile

from generate_traffic import Traffic_Generator
from model import TestModel
from visualization import Visualization
from utils import import_test_configuration, set_sumo, set_test_path





class Test(Simulation):
    def __init__(self, Model, TrafficGen, sumo_cmd, max_steps, green_duration, yellow_duration, num_states,
                 num_actions):

        super().__init__(Model, TrafficGen, sumo_cmd, max_steps, green_duration,
                         yellow_duration, num_states, num_actions)

        self._reward_episode = []
        self._queue_length_episode = []

    def run(self, episode):
        """
        Runs the testing simulation
        """
        start_time = timeit.default_timer()

        # first, generate the route file for this simulation and set up sumo
        self._TrafficGen.generate_traffic(episode)
        traci.start(self._sumo_cmd)
        print("Simulating...")

        # inits
        self._step = 0
        self._waiting_times = {}
        old_total_wait = 0
        old_action = -1  # dummy init

        while self._step < self._max_steps:
            # get current state of the intersection
            current_state = self._get_state()

            # calculate reward of previous action: (change in cumulative waiting time between actions) waiting time =
            # seconds waited by a car since the spawn in the environment, cumulated for every car in incoming lanes
            current_total_wait = self._collect_waiting_times()
            reward = old_total_wait - current_total_wait

            # choose the light phase to activate, based on the current state of the intersection
            action = self._choose_action(current_state)
            self._set_phase_and_simulate(old_action, action)

            # saving variables for later & accumulate reward
            old_action = action
            old_total_wait = current_total_wait

            self._reward_episode.append(reward)

        traci.close()
        simulation_time = round(timeit.default_timer() - start_time, 1)

        return simulation_time

    def _simulate(self, steps_todo):
        """
        Proceed with the simulation in sumo
        """
        if (
                self._step + steps_todo) >= self._max_steps:  # do not do more steps than the maximum allowed number of steps
            steps_todo = self._max_steps - self._step

        while steps_todo > 0:
            traci.simulationStep()  # simulate 1 step in sumo
            self._step += 1  # update the step counter
            steps_todo -= 1
            queue_length = self._get_queue_length()
            self._queue_length_episode.append(queue_length)

    def _choose_action(self, state):
        """
        Decide wheter to perform an explorative or exploitative action, according to an epsilon-greedy policy
        """
        return np.argmax(self._Model.predict_one(state))

    @property
    def queue_length_episode(self):
        return self._queue_length_episode

    @property
    def reward_episode(self):
        return self._reward_episode


if __name__ == "__main__":

    config = import_test_configuration(config_file='testing_settings.ini')
    sumo_cmd = set_sumo(config['gui'], config['simulation_folder'], config['sumocfg_file_name'], config['max_steps'])
    model_path, plot_path = set_test_path(config['models_path_name'], config['model_to_test'])

    Model = TestModel(
        input_dim=config['num_states'],
        model_path=model_path
    )

    Traffic_Generator = Traffic_Generator(
        config["flow_file"],
        config["route_file"],
        config["n_cars_generated"],
        config["simulation_time"]
    )

    Visualization = Visualization(
        plot_path,
        dpi=96
    )

    Test = Test(
        Model,
        Traffic_Generator,
        sumo_cmd,
        config['max_steps'],
        config['green_duration'],
        config['yellow_duration'],
        config['num_states'],
        config['num_actions']
    )

    print('\n----- Test episode')
    simulation_time = Test.run(config['episode_seed'])  # run the simulation
    print('Simulation time:', simulation_time, 's')

    print("----- Testing info saved at:", plot_path)

    copyfile(src='testing_settings.ini', dst=os.path.join(plot_path, 'testing_settings.ini'))

    Visualization.save_data_and_plot(data=Test.reward_episode, filename='reward', xlabel='Action step', ylabel='Reward')
    Visualization.save_data_and_plot(data=Test.queue_length_episode, filename='queue', xlabel='Step', ylabel='Queue lenght (vehicles)')
