class MemoryReader:
    def __init__(self, citra):
        self.citra = citra

    def read(self, address, size):
        return self.citra.read_memory(
            address,
            size
        )