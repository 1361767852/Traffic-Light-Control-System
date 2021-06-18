import json
from itertools import product

inter = {
    'gneJ6': 3,
    'gneJ7': 3
}


class Map:

    def __init__(self, filename):

        info = self._parse_file(filename)

        self.roads = info['roads']
        self.lane_groups = info['lane_groups']
        self.states = self._build_actions(info['num_states'])

    def _parse_file(self, filename):

        with open(filename) as file:
            content = file.read()

        return json.loads(content)

    def _flatten(self, lis):

        """
		Transform a nested list to a 1D list 
		"""

        result = []
        for item in lis:

            if isinstance(item, list):
                result = result + self._flatten(item)
            else:
                result.append(item)

        return result

    def _build_actions(self, intersections):

        """
		Return all possible actions
		"""

        # First we generate all possible combinations

        # we have to init the first value

        keys = list(intersections.keys())

        num_states = intersections[keys[0]]

        # we multiply by two because in the .net file odd values represent yellow phases
        result = list(map(lambda x: 2 * x, range(num_states)))

        result = [[x] for x in result]

        # now we do the prodcut with other states if there are any

        for i in range(1, len(keys)):

            new_result = []

            for res in result:
                num_states = intersections[keys[i]]

                states = list(map(lambda x: 2 * x, range(num_states)))

                prod = list(product([res], states))
                prod = list(map(lambda x: list(x), prod))

                new_result = new_result + prod

            result = new_result

        result = list(map(lambda x: self._flatten(x), result))

        # Now we build the dict

        for j, res in enumerate(result):
            state = {}
            for i in range(len(res)):
                key = keys[i]
                state[key] = res[i]

            result[j] = state

        return result


if __name__ == '__main__':
    maps = Map("map.json")

    print(maps.states)
    print(maps.roads)
    print(maps.lane_groups)
