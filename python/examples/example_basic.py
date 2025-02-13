from pyabc import *
import logging

p = ABCProgram(logging.DEBUG, backend=ABCBackend.MLIRText)
# p = ABCProgram(logging.DEBUG)

with ABCContext(p, logging.DEBUG):
    def main():
        a = 1
        if a * a < a:
            return 20

        s = 0
        for i in range(10):
            s += i
        return s

if __name__ == "__main__":
    # TODO: Printing MLIR for the moment, remove when we actually execute it.
    with open("example_basic.mlir", "w") as f:
        p.dump(f)
