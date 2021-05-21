import matplotlib.pyplot as plt


if __name__ == '__main__':

	with open("plot_queue_data.txt", 'r') as file:
		tfo = file.readlines()

	with open("plot_queue_ttl_data.txt", 'r') as file:
		ttl = file.readlines()


	tfo = list(map(lambda x : int(x), tfo))
	ttl = list(map(lambda x : int(x), ttl))

	plt.plot(tfo, 'b', label="Our System")
	plt.plot(ttl, 'r', label="Traditional Traffic System")

	plt.legend(["Our System", "Traditional Traffic Light System"])

	plt.ylabel("Queue Length")
	plt.xlabel("Time (seconds)")

	plt.show()



