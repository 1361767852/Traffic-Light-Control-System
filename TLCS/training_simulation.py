import traci
import numpy as np
import random
import timeit


lane_groups = [

    ["gneE4_0", "gneE4_1"],

    ["gneE5_0"],
    ["gneE5_1"],

    ["gneE6_0"],
    ["gneE6_1"],

    ["-gneE4_0"],
    ["-gneE4_1"],

    ["gneE8_0"],
    ["gneE8_1"],

    ["gneE9_0"],
    ["gneE9_1"],   
]

Roads = ["gneE4","-gneE4", "gneE5", "gneE6", "gneE8", "gneE9"]


def action_to_phase(code):
    if code == 0:
        return {"gneJ6": 0, "gneJ7": 0}
    if code == 1:
        return {"gneJ6": 0, "gneJ7": 2}
    if code == 2:
        return {"gneJ6": 0, "gneJ7": 4}
    if code == 3:
        return {"gneJ6": 2, "gneJ7": 0}
    if code == 4:
        return {"gneJ6": 2, "gneJ7": 2}
    if code == 5:
        return {"gneJ6": 2, "gneJ7": 4}
    if code == 6:
        return {"gneJ6": 4, "gneJ7": 0}
    if code == 7:
        return {"gneJ6": 4, "gneJ7": 2}
    if code == 8:
        return {"gneJ6": 4, "gneJ7": 4}




class Simulation:
    def __init__(self, Model, Memory, TrafficGen, sumo_cmd, gamma, max_steps, green_duration, yellow_duration,
                 num_states, num_actions, training_epochs):
        self._Model = Model
        self._Memory = Memory
        self._TrafficGen = TrafficGen
        self._gamma = gamma
        self._step = 0
        self._sumo_cmd = sumo_cmd
        self._max_steps = max_steps
        self._green_duration = green_duration
        self._yellow_duration = yellow_duration
        self._num_states = num_states
        self._num_actions = num_actions
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

        old_queue = 0

        while self._step < self._max_steps:

            # get current state of the intersection
            current_state = self._get_state()


            # calculate reward of previous action: (change in cumulative waiting time between actions)
            # waiting time = seconds waited by a car since the spawn in the environment,
            # cumulated for every car in incoming lanes
            current_total_wait = self._collect_waiting_times()

            #queue = self._get_queue_length()
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
            #old_queue = queue

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


    def _collect_waiting_times(self):
        """
        Retrieve the waiting time of every car in the incoming roads
        """
        waiting_time = 0
        car_list = traci.vehicle.getIDList()

        for car_id in car_list:
            waiting_time += traci.vehicle.getAccumulatedWaitingTime(car_id)

        return waiting_time

    def _collect_waiting_times(self):
        """
        Retrieve the waiting time of every car in the incoming roads
        """
        car_list = traci.vehicle.getIDList()
        for car_id in car_list:
            wait_time = traci.vehicle.getAccumulatedWaitingTime(car_id)
            road_id = traci.vehicle.getRoadID(car_id)  # get the road id where the car is located
            if road_id in Roads:  # consider only the waiting times of cars in incoming roads
                self._waiting_times[car_id] = wait_time
            else:
                if car_id in self._waiting_times: # a car that was tracked has cleared the intersection
                    del self._waiting_times[car_id] 
        total_waiting_time = sum(self._waiting_times.values())
        return total_waiting_time


    def _choose_action(self, state, epsilon):
        """
        Decide wheter to perform an explorative or exploitative action, according to an epsilon-greedy policy
        """
        if random.random() < epsilon:
            return random.randint(0, self._num_actions - 1)  # random action
        else:
            return np.argmax(self._Model.predict_one(state))  # the best action given the current state

    
    def _get_changed_actions(self, old_action_number, action_number):

        changed = []
        old_actions = action_to_phase(old_action_number)
        actions = action_to_phase(action_number)

        for j in actions:
            if actions[j] != old_actions[j]:
                changed.append(j)
        return changed
    
    def _set_phase_and_simulate(self, old_action_number, action_number):

        phase_duration = self._green_duration

        # if the chosen phase is different from the last phase, activate the yellow phase
        if self._step != 0 and old_action_number != action_number:
            self._set_yellow_phase(old_action_number, action_number)
            self._simulate(self._yellow_duration)
            phase_duration = self._green_duration - self._yellow_duration

        coresp = action_to_phase(action_number)
        for tls_id in coresp:
            traci.trafficlight.setPhase(tls_id, coresp[tls_id])
        
        self._simulate(phase_duration)

    def _set_yellow_phase(self, old_action_number, action_number):
        """
        Activate the correct yellow light combination in sumo
        """
        changed = self._get_changed_actions(old_action_number, action_number)

        for tlsID in traci.trafficlight.getIDList():
            if tlsID in changed:
                yellow_phase_code = action_to_phase(old_action_number)[tlsID] + 1
                traci.trafficlight.setPhase(tlsID, yellow_phase_code)
            else:
                phase_code = action_to_phase(action_number)[tlsID]
                traci.trafficlight.setPhase(tlsID, phase_code)

    def _get_queue_length(self):
        """
        Retrieve the number of cars with speed = 0 in every incoming lane
        """
        queue_length = 0
        for id in Roads:
            queue_length += traci.edge.getLastStepHaltingNumber(id)

        return queue_length


    def _get_state(self):
        """
        Retrieve the state of the intersection from sumo, in the form of cell occupancy
        """
        state = np.zeros(self._num_states)
        
        for i, group in enumerate(lane_groups):
            for lane_id in group :
                state[i] += traci.lane.getLastStepHaltingNumber(lane_id)
        
        return state

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
