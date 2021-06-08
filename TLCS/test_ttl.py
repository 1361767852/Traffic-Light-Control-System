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


class Test_TTL(Simulation):
    def __init__(self, TrafficGen, sumo_cmd, max_steps, green_duration, yellow_duration, num_states,
                 num_actions):

        super().__init__(None, TrafficGen, sumo_cmd, max_steps, green_duration,
                         yellow_duration, num_states, num_actions)

        self._reward_episode = []
        self._queue_length_episode = []
        self._CO2_episode = []
        self._fuel_episode = []

    def run(self, episode):
        """
        Runs the testing simulation
        """
        start_time = timeit.default_timer()

        self._TrafficGen.generate_traffic(episode)
        traci.start(self._sumo_cmd)
        print("Simulating...")

        # inits
        self._step = 0
        self._waiting_times = {}
        old_total_wait = 0
        old_action = -1  # dummy init

        while self._step < self._max_steps:

            self._collect_waiting_times()

            self._simulate(self._green_duration)


        traci.close()
        simulation_time = round(timeit.default_timer() - start_time, 1)

        return simulation_time

    def _simulate(self, steps_todo):
        """
        Proceed with the simulation in sumo
        """
        if (self._step + steps_todo) >= self._max_steps:
            steps_todo = self._max_steps - self._step

        while steps_todo > 0:
            traci.simulationStep()  # simulate 1 step in sumo
            self._step += 1  # update the step counter
            steps_todo -= 1
            queue_length = self._get_queue_length()
            self._queue_length_episode.append(queue_length)

            fuel = self._get_fuel()
            self._fuel_episode.append(fuel)
            
            CO2_emission = self._get_CO2()
            self._CO2_episode.append(CO2_emission)

    @property
    def queue_length_episode(self):
        return self._queue_length_episode

    @property
    def reward_episode(self):
        return self._reward_episode
    
    @property
    def CO2_episode(self):
        return self._CO2_episode

    @property
    def fuel_episode(self):
        return self._fuel_episode
    
    @property
    def waiting_times(self):
        return self._get_waiting_times()


if __name__ == "__main__":
    config = import_test_configuration(config_file='settings/testing_ttl_settings.ini')
    sumo_cmd = set_sumo(config['gui'], config['simulation_folder'], config['sumocfg_file_name'], config['max_steps'])
    model_path, plot_path = set_test_path(config['models_path_name'], config['model_to_test'])

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

    Test = Test_TTL(
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

    copyfile(src='settings/testing_ttl_settings.ini', dst=os.path.join(plot_path, 'testing_ttl_settings.ini'))

    Visualization.save_data_and_plot(data=Test.queue_length_episode, filename='queue_ttl', xlabel='Step',
                                    ylabel='Queue length (vehicles)')
    Visualization.save_data_and_plot(data=Test.CO2_episode, filename='CO2_ttl', xlabel='Step',
                                    ylabel='CO2 emission (mg)')

    Visualization.save_data_and_plot(data=Test.fuel_episode, filename='fuel_ttl', xlabel='Step',
                                     ylabel='fuel consumption (ml)')

    Visualization.save_data_and_plot(data=Test.waiting_times, filename='waiting_time_ttl', xlabel='Step',
                                     ylabel='waiting_times (seconds)')
