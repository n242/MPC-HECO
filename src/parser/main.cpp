#include <iostream>
#include "module.hpp"
#include "standard_functions.hpp"

int main() {
	std::string path = __FILE__;
	path = path.substr(0, path.find_last_of("/\\") + 1) + "test.stk";
	
	using namespace stork;
	
	module m;
	
	add_standard_functions(m);

	auto s_main = m.create_public_function_caller<void>("main");
	
	if (m.try_load(path.c_str(), &std::cerr)) {
		s_main();
	}
	
	return 0;
}
