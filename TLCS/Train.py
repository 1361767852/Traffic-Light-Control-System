from __future__ import absolute_import
from __future__ import print_function

import traci
import numpy as np
import random
import timeit
from Simulation import Simulation

import os
import datetime
from shutil import copyfile

from generate_traffic import Traffic_Generator
from memory import Memory
from model import TrainModel
from visualization import Visualization
from utils import import_train_configuration, set_sumo, set_train_path


class Train(Simulation):
    def __init__(self, Model, Memory, TrafficGen, sumo_cmd, gamma, max_steps, green_duration, yellow_duration,
                 num_states, num_actions, training_epochs):

        super().__init__(Model, TrafficGen, sumo_cmd, max_steps, green_duration,
                         yellow_duration, num_states, num_actions)

        self._Memory = Memory
        self._gamma = gamma
        self._reward_store = []
        self._cumulative_wait_store = []
        self._avg_queue_length_store = []
        self._training_epochs = training_epochs

    def run(self, episode, epsilon):
        """
        Runs an episode of simulation, then starts a training session
        """
        start_time = timeit.default_timer()

        # first, generate the route file for this simulation and set up sumo

        self._TrafficGen.generate_traffic(episode)

        # self._TrafficGen.generate_traffic(seed=episode)
        traci.start(self._sumo_cmd)
        print("Simulating...")

        # inits
        self._waiting_times = {}
        self._step = 0
        self._sum_neg_reward = 0
        self._sum_queue_length = 0
        self._sum_waiting_time = 0
        old_total_wait = 0
        old_state = -1
        old_action = -1

        while self._step < self._max_steps:

            # get current state of the intersection
            current_state = self._get_state()

            # calculate reward of previous action: (change in cumulative waiting time between actions)
            # waiting time = seconds waited by a car since the spawn in the environment,
            # cumulated for every car in incoming lanes
            current_total_wait = self._collect_waiting_times()

            # queue = self._get_queue_length()
            reward = old_total_wait - current_total_wait

            # saving the data into the memory
            if self._step != 0:
                self._Memory.add_sample((old_state, old_action, reward, current_state))

            # choose the light phase to activate, based on the current state of the intersection
            action = self._choose_action(current_state, epsilon)

            self._set_phase_and_simulate(old_action, action)

            # saving variables for later & accumulate reward
            old_state = current_state
            old_action = action
            old_total_wait = current_total_wait
            # old_queue = queue

            # saving only the meaningful reward to better see if the agent is behaving correctly
            if reward < 0:
                self._sum_neg_reward += reward

        self._save_episode_stats()
        print("Total reward:", self._sum_neg_reward, "- Epsilon:", round(epsilon, 2))
        traci.close()
        simulation_time = round(timeit.default_timer() - start_time, 1)

        print("Training...")
        start_time = timeit.default_timer()
        for _ in range(self._training_epochs):
            self._replay()
        training_time = round(timeit.default_timer() - start_time, 1)

        return simulation_time, training_time

    def _simulate(self, steps_todo):
        """
        Execute steps in sumo while gathering statistics
        """
        # do not do more steps than the maximum allowed number of steps
        if (self._step + steps_todo) >= self._max_steps:
            steps_todo = self._max_steps - self._step

        while steps_todo > 0:
            traci.simulationStep()  # simulate 1 step in sumo
            self._step += 1  # update the step counter
            steps_todo -= 1
            queue_length = self._get_queue_length()
            self._sum_queue_length += queue_length
            # 1 step while wating in queue means 1 second waited,
            # for each car, therefore queue_lenght == waited_seconds
            self._sum_waiting_time += queue_length

    def _choose_action(self, state, epsilon):
        """
        Decide wheter to perform an explorative or exploitative action, according to an epsilon-greedy policy
        """
        if random.random() < epsilon:
            return random.randint(0, self._num_actions - 1)  # random action
        else:
            return np.argmax(self._Model.predict_one(state))  # the best action given the current state

    def _replay(self):
        """
        Retrieve a group of samples from the memory and for each of them update the learning equation, then train
        """
        batch = self._Memory.get_samples(self._Model.batch_size)

        if len(batch) > 0:  # if the memory is full enough
            states = np.array([val[0] for val in batch])  # extract states from the batch
            next_states = np.array([val[3] for val in batch])  # extract next states from the batch

            # prediction
            q_s_a = self._Model.predict_batch(states)  # predict Q(state), for every sample
            q_s_a_d = self._Model.predict_batch(next_states)  # predict Q(next_state), for every sample

            # setup training arrays
            x = np.zeros((len(batch), self._num_states))
            y = np.zeros((len(batch), self._num_actions))

            for i, b in enumerate(batch):
                state, action, reward, _ = b[0], b[1], b[2], b[3]  # extract data from one sample
                current_q = q_s_a[i]  # get the Q(state) predicted before
                current_q[action] = reward + self._gamma * np.amax(q_s_a_d[i])  # update Q(state, action)
                x[i] = state
                y[i] = current_q  # Q(state) that includes the updated action value

            self._Model.train_batch(x, y)  # train the NN

    def _save_episode_stats(self):
        """
        Save the stats of the episode to plot the graphs at the end of the session
        """
        self._reward_store.append(self._sum_neg_reward)  # how much negative reward in this episode
        self._cumulative_wait_store.append(
            self._sum_waiting_time)  # total number of seconds waited by cars in this episode
        self._avg_queue_length_store.append(
            self._sum_queue_length / self._max_steps)  # average number of queued cars per step, in this episode

    @property
    def reward_store(self):
        return self._reward_store

    @property
    def cumulative_wait_store(self):
        return self._cumulative_wait_store

    @property
    def avg_queue_length_store(self):
        return self._avg_queue_length_store


if __name__ == "__main__":

    config = import_train_configuration(config_file='training_settings.ini')
    sumo_cmd = set_sumo(config['gui'], config['simulation_folder'], config['sumocfg_file_name'], config['max_steps'])
    path = set_train_path(config['models_path_name'])

    Model = TrainModel(
        config['num_layers'],
        config['width_layers'],
        config['batch_size'],
        config['learning_rate'],
        input_dim=config['num_states'],
        output_dim=config['num_actions']
    )

    Memory = Memory(
        config['memory_size_max'],
        config['memory_size_min']
    )

    Traffic_Generator = Traffic_Generator(
        config["flow_file"],
        config["route_file"],
        config["n_cars_generated"],
        config["simulation_time"]
    )

    Visualization = Visualization(
        path,
        dpi=96
    )

    Train = Train(
        Model,
        Memory,
        Traffic_Generator,
        sumo_cmd,
        config['gamma'],
        config['max_steps'],
        config['green_duration'],
        config['yellow_duration'],
        config['num_states'],
        config['num_actions'],
        config['training_epochs']
    )

    episode = 0
    timestamp_start = datetime.datetime.now()

    while episode < config['total_episodes']:
        print('\n----- Episode', str(episode + 1), 'of', str(config['total_episodes']))
        epsilon = 1.0 - (episode / config[
            'total_episodes'])  # set the epsilon for this episode according to epsilon-greedy policy
        simulation_time, training_time = Train.run(episode, epsilon)  # run the simulation
        print('Simulation time:', simulation_time, 's - Training time:', training_time, 's - Total:',
              round(simulation_time + training_time, 1), 's')
        episode += 1

    print("\n----- Start time:", timestamp_start)
    print("----- End time:", datetime.datetime.now())
    print("----- Session info saved at:", path)

    Model.save_model(path)

    copyfile(src='training_settings.ini', dst=os.path.join(path, 'training_settings.ini'))

    Visualization.save_data_and_plot(data=Train.reward_store, filename='reward', xlabel='Episode',
                                     ylabel='Cumulative negative reward')
    Visualization.save_data_and_plot(data=Train.cumulative_wait_store, filename='delay', xlabel='Episode',
                                     ylabel='Cumulative delay (s)')
    Visualization.save_data_and_plot(data=Train.avg_queue_length_store, filename='queue', xlabel='Episode',
                                     ylabel='Average queue length (vehicles)')
