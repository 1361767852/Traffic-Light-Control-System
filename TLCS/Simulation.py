import traci
import numpy as np
import random
import timeit


class Simulation:
    def __init__(self, Model, TrafficGen, sumo_cmd, max_steps, green_duration, yellow_duration, num_states,
                 num_actions):
        self._Model = Model
        self._TrafficGen = TrafficGen
        self._step = 0
        self._sumo_cmd = sumo_cmd
        self._max_steps = max_steps
        self._green_duration = green_duration
        self._yellow_duration = yellow_duration
        self._num_states = num_states
        self._num_actions = num_actions

        self._reward_episode = []
        self._queue_length_episode = []
        self._Roads = ["gneE4", "-gneE4", "gneE5", "gneE6", "gneE8", "gneE9"]
        self._lane_groups = [

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

    def action_to_phase(self, code):
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

    def _collect_waiting_times(self):
        """
        Retrieve the waiting time of every car in the incoming roads
        """
        car_list = traci.vehicle.getIDList()
        for car_id in car_list:
            wait_time = traci.vehicle.getAccumulatedWaitingTime(car_id)
            road_id = traci.vehicle.getRoadID(car_id)  # get the road id where the car is located
            if road_id in self._Roads:  # consider only the waiting times of cars in incoming roads
                self._waiting_times[car_id] = wait_time
            else:
                if car_id in self._waiting_times:  # a car that was tracked has cleared the intersection
                    del self._waiting_times[car_id]
        total_waiting_time = sum(self._waiting_times.values())
        return total_waiting_time

    def _get_changed_actions(self, old_action_number, action_number):

        changed = []
        old_actions = self.action_to_phase(old_action_number)
        actions = self.action_to_phase(action_number)

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

        coresp = self.action_to_phase(action_number)
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
                yellow_phase_code = self.action_to_phase(old_action_number)[tlsID] + 1
                traci.trafficlight.setPhase(tlsID, yellow_phase_code)
            else:
                phase_code = self.action_to_phase(action_number)[tlsID]
                traci.trafficlight.setPhase(tlsID, phase_code)

    def _get_queue_length(self):
        """
        Retrieve the number of cars with speed = 0 in every incoming lane
        """
        queue_length = 0
        for id in self._Roads:
            queue_length += traci.edge.getLastStepHaltingNumber(id)

        return queue_length

    def _get_state(self):
        """
        Retrieve the state of the intersection from sumo, in the form of cell occupancy
        """
        state = np.zeros(self._num_states)

        for i, group in enumerate(self._lane_groups):
            for lane_id in group:
                state[i] += traci.lane.getLastStepHaltingNumber(lane_id)

        return state
