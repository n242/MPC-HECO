#include <complex>

#include "DotProduct.h"
#include "BenchmarkHelper.h"

int main(int argc, char *argv[]) {
  if (argc < 2) {
    std::cout << "USAGE: dp-bench [version]" << std::endl;
    std::cout << "       versions:" << std::endl;
    std::cout << "          - Porcupine" << std::endl;
    std::cout << "          - HECO" << std::endl;
    std::cout << "          - Naive" << std::endl;

    std::exit(1);
  }

  // Create two vectors of bits (booleans),
  size_t poly_modulus_degree = 2 << 12;
  std::vector<int> a(8);
  getRandomVector(a);
  std::vector<int> b(8);
  getRandomVector(b);

  BENCH_FUNCTION(DotProduct, Porcupine, encryptedDotProductPorcupine, a, b);
  BENCH_FUNCTION(DotProduct, HECO, encryptedDotProductBatched, a, b);
  BENCH_FUNCTION(DotProduct, Naive, encryptedDotProductNaive, a, b);

  return 0;
}