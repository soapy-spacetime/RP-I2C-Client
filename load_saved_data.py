import pickle

filename = "2021-03-05 Nim's first run.pkl"
file = open(filename, "rb")
pkl = pickle.load(file)

Meta = pkl['Meta']
Data = pkl['Data']


print(Meta)
print("Datapoints: %d" % len(Data))