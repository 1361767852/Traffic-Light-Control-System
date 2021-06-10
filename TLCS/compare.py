import matplotlib.pyplot as plt
import os
import numpy as np

num_model = 1
path = "models/model_" + str(num_model) + "/test/"



def addlabels(x,y):
    for i in range(len(x)):
        plt.text(i, y[i], y[i], ha = 'center')



def plot(desc_file, ylabel_graph, ylabel_bar):

	with open(path + "plot_"+desc_file+"_data.txt", 'r') as file:
		tfo = file.readlines()

	with open(path + "plot_"+desc_file+"_ttl_data.txt", 'r') as file:
		ttl = file.readlines()

	with open(path + "plot_"+desc_file+"_one_data.txt", 'r') as file:
		one = file.readlines()


	tfo = list(map(lambda x : float(x), tfo))
	ttl = list(map(lambda x : float(x), ttl))
	one = list(map(lambda x : float(x), one))

	
	plt.plot(one, 'r', label="One at a time")
	plt.plot(ttl, 'b', label="Traditional Traffic System")
	plt.plot(tfo, 'g', label="Our System")


	plt.legend(["One at a time", "Traditional Traffic Light System", "Our System"])

	plt.ylabel(ylabel_graph)
	plt.xlabel("Time (seconds)")

	plt.show()


	x = ["One at a time", "Traditional Traffic\n Light System", "Our System"]
	y = [np.average(one), np.average(ttl), np.average(tfo)]

	
	plt.bar(x, y)

	addlabels(x,y)

	plt.ylabel(ylabel_bar)

	plt.show()



if __name__ == '__main__':

	plot("queue", "Queue Length", "Average queue length")
	plot("CO2", "CO2 emission (mg)", "Average CO2 emission (mg)")
	plot("waiting_time", "Waiting_time (seconds)", "Average waiting_time (seconds)")
	plot("fuel", "Fuel consumption (ml)", "Average fuel consumption (ml)")

	