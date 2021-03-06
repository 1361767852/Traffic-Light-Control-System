import traci
import numpy as np


class Simulation:
    def __init__(self, Model, Map_info, TrafficGen, sumo_cmd, max_steps, green_duration, yellow_duration, num_states,
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

        self._waiting_times = {}

        self._all_cars_waiting_time = {}

        self._map_info = Map_info
        self._Roads = self._map_info.roads
        self._lane_groups = self._map_info.lane_groups

    def action_to_state(self, code):
        return self._map_info.states[code]

    def _collect_waiting_times(self):
        """
        Retrieve the waiting time of every car in the incoming roads
        """
        car_list = traci.vehicle.getIDList()
        for car_id in car_list:
            wait_time = traci.vehicle.getAccumulatedWaitingTime(car_id)
            road_id = traci.vehicle.getRoadID(car_id)  # get the road id where the car is located
            if road_id in self._Roads:  # consider only the waiting times of cars in incoming roads
                self._all_cars_waiting_time[car_id] = wait_time
                self._waiting_times[car_id] = wait_time
            else:
                if car_id in self._waiting_times:  # a car that was tracked has cleared the intersection
                    del self._waiting_times[car_id]
        total_waiting_time = sum(self._waiting_times.values())
        return total_waiting_time

    def _get_changed_actions(self, old_action_number, action_number):

        changed = []
        old_actions = self.action_to_state(old_action_number)
        actions = self.action_to_state(action_number)

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

        coresp = self.action_to_state(action_number)
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
                yellow_phase_code = self.action_to_state(old_action_number)[tlsID] + 1
                traci.trafficlight.setPhase(tlsID, yellow_phase_code)
            else:
                phase_code = self.action_to_state(action_number)[tlsID]
                traci.trafficlight.setPhase(tlsID, phase_code)

    def _get_queue_length(self):
        """
        Retrieve the number of cars with speed = 0 in every incoming lane
        """
        queue_length = 0
        for id in self._Roads:
            queue_length += traci.edge.getLastStepHaltingNumber(id)

        return queue_length

    def _get_CO2(self):
        """
        Retrieve co2 on the edges
        """
        co2 = 0
        for id in self._Roads:
            co2 += traci.edge.getCO2Emission(id)
        return co2

    def _get_fuel(self):
        """
        Retrieve co2 on the edges
        """
        fuel = 0
        for id in self._Roads:
            fuel += traci.edge.getFuelConsumption(id)
        return fuel

    def _get_waiting_times(self):
        """
        get list of waiting times of the cars 
        """
        return list(self._all_cars_waiting_time.values())

    def _get_state(self):
        """
        Retrieve the state of the intersection from sumo, in the form of cell occupancy
        """
        state = np.zeros(self._num_states)

        for i, group in enumerate(self._lane_groups):
            for lane_id in group:
                state[i] += traci.lane.getLastStepHaltingNumber(lane_id)

        return state
