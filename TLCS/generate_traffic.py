from xml.dom import minidom
from xml.dom.minidom import Node, Document
import numpy as np
import json


class Traffic_Generator:

	def __init__(self, CONNECTION_FILE, OUT_FILE, CAR_NUMBER, SIMULATION_TIME):

		
		self.CONNECTION_FILE = CONNECTION_FILE
		self.OUT_FILE = OUT_FILE
		self.CAR_NUMBER = CAR_NUMBER
		self.SIMULATION_TIME = SIMULATION_TIME # in seconds

		#self.CONNECTION_FILE = "traffic_flow/ain_naadja_flow.json"
		#self.OUT_FILE = "ain_naadja.rou.xml"
		#self.CAR_NUMBER = 3800
		#self.SIMULATION_TIME = 3600 # in seconds
		self.arrival_rate = self.CAR_NUMBER/ self.SIMULATION_TIME

		self.EMERGENCY_PROBABILITY = 0.005

		self.doc = None
		self.connections = {}

		



	def initialize_doc(self):

		doc = Document()

		root = doc.createElement("routes")
		root.setAttribute("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
		root.setAttribute("xsi:noNamespaceSchemaLocation", "http://sumo.dlr.de/xsd/routes_file.xsd")

		doc.appendChild(root)

		# add vehicls types

		vType = doc.createElement("vType")
		vType.setAttribute("id", "veh_passenger")
		vType.setAttribute("vClass", "passenger")

		root.appendChild(vType)

		vType = doc.createElement("vType")
		vType.setAttribute("id", "veh_emergency")
		vType.setAttribute("vClass", "passenger")
		vType.setAttribute("color", "red")
		vType.setAttribute("width", "2.5")

		root.appendChild(vType)
		
		return doc


	def get_connections(self, file):

		with open(file) as file:
			connections = json.loads(file.read())

		# We sort the connections from the least probable to the most probable
		for i in connections:
			if i != "start":

				for j in range(len(connections[i])):
					connections[i][j]["probability"] = float(connections[i][j]["probability"] )
				connections[i].sort(key = lambda x: x["probability"])

		return connections


	
	def choose_start(self):
		start_edges = self.connections["start"]

		pb = np.random.random()
		for edge in start_edges:
			if pb <= float(start_edges[edge]):
				return edge




	def generate_path(self):

		start = self.choose_start()
		path = [start]
		edge = start

		while self.connections.get(edge):
			
			pb = np.random.random()
			nexts = self.connections[edge]

			# the probabilities are sorted
			for i in range(len(nexts)):

				if pb < nexts[i]["probability"] or i == len(nexts) - 1 :

					edge = nexts[i]["edge"]
					path.append(edge)
					break

		return path




	def add_cars(self, n_cars, car_id, time):


		times = np.random.random(n_cars)
		times = sorted(list(map(lambda x : np.around(time + x), times)))

		for n in range(n_cars):

			
			path = " ".join(self.generate_path())

			vehicle = self.doc.createElement("vehicle")
			vehicle.setAttribute("id", "veh" + str(car_id + n))

			is_emergency = np.random.random()

			if is_emergency < self.EMERGENCY_PROBABILITY :
				vehicle.setAttribute("type", "veh_emergency")
			else:
				vehicle.setAttribute("type", "veh_passenger")

			vehicle.setAttribute("depart", str(times[n]))
			vehicle.setAttribute("departLane", "best")
			vehicle.setAttribute("departSpeed", "max")

			roote = self.doc.createElement("route")
			roote.setAttribute("edges", path)

			vehicle.appendChild(roote)
			self.doc.documentElement.appendChild(vehicle)


		
	def generate_cars(self):

		car_id = 0
		time = 0

		# arrivals follow a poisson distribution
		arrivals = np.random.poisson(self.arrival_rate, self.SIMULATION_TIME)

		for n_cars in arrivals:

			self.add_cars(n_cars, car_id, time)

			car_id += n_cars
			time += 1



	def generate_traffic(self, seed):

		np.random.seed(seed)

		self.doc = self.initialize_doc()
		self.connections = self.get_connections(self.CONNECTION_FILE)

		self.generate_cars()

		xml_file = self.doc.toprettyxml()

		with open(self.OUT_FILE, 'w') as file :
			file.write(xml_file)




if __name__ == "__main__":

	CONNECTION_FILE = "intersection/four/four_flow.json"
	OUT_FILE = "intersection/four/four.rou.xml"
	CAR_NUMBER = 2100
	SIMULATION_TIME = 2000 # in seconds

	t = Traffic_Generator(CONNECTION_FILE, OUT_FILE, CAR_NUMBER, SIMULATION_TIME)
	t.generate_traffic(5)

