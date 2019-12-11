# FHE Code Optimizer

This repository hosts an optimizer for Fully Homomorphic Encryption (FHE) working on the basis of Abstract Syntax Trees (ASTs).

For future work, this optimization component should be integrated into the [Marble](https://github.com/MarbleHE/Marble) FHE compiler.

## Features

The features of this tool can roughly be divided into two parts: 
The computation of code-based **statistics** that are relevant for FHE-based optimizations (e.g., multiplicative depth, noise growth), and performing **optimizations** on the AST.

### Statistics


### Optimizations


## AST Representation

The AST to be used as foundation for FHE optimizations consists of nodes that are derived from either `AbstractExpr` or `AbstractStatement`, depending on whether the operation is an expression or a statement, respectively.

- `AbstractExpr`
    - `BinaryExpr` – a binary expression 
    - `Call` – a call to an internal function, i.e., its implementation is represented in the AST.
    - `CallExternal` – a call to an external function which is treated as "black box", i.e., without looking into its definition.
    - `FunctionParameter` – 
    - `Group` – 
    - `Literal` – 
    - `LiteralBool` – 
    - `LiteralInt` – 
    - `LiteralString` – 
    - `LogicalExpr` – 
    - `UnaryExpr` – 
- `AbstractStatement`
    - `Block` – a code block `{...}`, e.g., the then-clause of an if statement.
    - `Class` – a class 
    - `Call` – see above.
    - `CallExternal` –  see above.
    - `Function` – a function definition.
    - `If` – an if-conditional statement.
    - `Return` – a return statement of a method.
    - `VarAssignm` – the assignment of a variable.
    - `VarDecl` – a variable declaration.
    - `While` – a while-loop.

## Getting Started

The following tools are required to get this project running:
- cmake (version ≥ 3.15) to build the project
    - tested with v3.15.5
- gcc or clang to compile the sources
    - tested with Apple clang v11.0.0
- doxygen to build the documentation files (html)
    - tested wth v1.8.16

The easiest way to use this library is to import the project into [CLion](https://www.jetbrains.com/clion/) which automatically loads the containing cmake build files and adds the respective targets.

Alternatively, you can build the project manually by running...


## Extending the Library

### Code Style

The code is written in C++ using [K&R style](https://en.wikipedia.org/wiki/Indentation_style#K&R_style). Classes are divided into implementation and header:

```
include/ast     – contains the header files (.h)
src/ast         – contains the implementation (.cpp)
```

For auto-formatting in the CLion IDE, please use the code style definition provided in [doc/clion/codestyle](doc/clion/codestyle).

#### Documentation

[Doxygen](http://www.doxygen.nl/manual/index.html) comments are used to create a documentation of this library. 
The documentation can be generated using the supplied configuration `doxygen.conf` as described following:

```bash
cd doc/doxygen
doxygen doxygen.conf
```

### Testing

The code is covered by unit tests to achieve high code quality and avoid introducing errors while extending the library.
For that, the [Google Test]() framework is used.
The library is automatically cloned from its GitHub repository using cmake, see [CMakeLists.txt](test/CMakeLists.txt).

The tests can be found in the [`test`](test/) directory.



