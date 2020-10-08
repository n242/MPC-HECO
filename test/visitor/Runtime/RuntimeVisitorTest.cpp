#include "include/ast_opt/ast/AbstractNode.h"
#include "include/ast_opt/parser/Parser.h"
#include "include/ast_opt/ast/Literal.h"
#include "include/ast_opt/visitor/runtime/RuntimeVisitor.h"
#include "include/ast_opt/visitor/runtime/SealCiphertextFactory.h"

#include "gtest/gtest.h"
#ifdef HAVE_SEAL_BFV
class RuntimeVisitorTest : public ::testing::Test {
 protected:
  std::unique_ptr<SealCiphertextFactory> scf;

  void SetUp() override {
    scf = std::make_unique<SealCiphertextFactory>(4096);
  }
};

TEST_F(RuntimeVisitorTest, testInputOutputAst) { /* NOLINT */
  // Test that checks whether we can pass input, run a very simple instruction, and retrieve the output.

  // program's input
  const char *inputs = R""""(
      secret int __input0__ = {43, 1, 1, 1, 22, 11, 425, 0, 1, 7};
      int __input1__ = {43, 1, 1, 1, 22, 11, 425, 0, 1, 0};
    )"""";
  auto astInput = Parser::parse(std::string(inputs));

  // program specification
  const char *program = R""""(
      __input0__ = rotate(__input0__, -4);
    )"""";
  auto astProgram = Parser::parse(std::string(program));

  // program's output
  const char *outputs = R""""(
      y = __input0__;
    )"""";
  auto astOutput = Parser::parse(std::string(outputs));

  // create a SpecialRuntimeVisitor instance
  SecretTaintedNodesMap secretTaintedNodesMap;
  RuntimeVisitor srv(*scf, *astInput, secretTaintedNodesMap);

  // run the program
  astProgram->accept(srv);

  std::unordered_map<std::string, std::vector<int64_t>> expectedOutput;
  std::vector<int64_t> data = {7, 7, 7, 7, 43, 1, 1, 1, 22, 11, 425, 0, 1, 7};
  expectedOutput.emplace("y", data);

  auto output = srv.getOutput(*astOutput);
  for (const auto &[identifier, ciphertext] : output) {
    std::vector<int64_t> decryptedValues;
    scf->decryptCiphertext(*ciphertext, decryptedValues);
    EXPECT_TRUE(expectedOutput.count(identifier) > 0);
    auto expected = expectedOutput.at(identifier);
    for (int i = 0; i < expected.size(); ++i) {
      EXPECT_EQ(expected[i], decryptedValues[i]);
    }
  }
}

TEST_F(RuntimeVisitorTest, testSimpleBinaryExpression) { /* NOLINT */

  // program's input
  const char *inputs = R""""(
      secret int __input0__ = {43, 1, 1, 1, 22, 11, 425, 0, 1, 7};
      int __input1__ = {43, 1, 1, 1, 22, 11, 425, 0, 1, 0};
    )"""";
  auto astInput = Parser::parse(std::string(inputs));

  // program specification
  const char *program = R""""(
      int sum = 10+25;
    )"""";
  auto astProgram = Parser::parse(std::string(program));

  // program's output
  const char *outputs = R""""(
      y = sum;
    )"""";
  auto astOutput = Parser::parse(std::string(outputs));

  // create a SpecialRuntimeVisitor instance
//  SecretTaintedNodesMap secretTaintedNodesMap;
  TypeCheckingVisitor typeCheckingVisitor;
  astProgram->accept(typeCheckingVisitor);

  auto map = typeCheckingVisitor.getSecretTaintedNodes();
  RuntimeVisitor srv(*scf, *astInput, map);

  // run the program
  astProgram->accept(srv);

//  std::unordered_map<std::string, std::vector<int64_t>> expectedOutput;
//  std::vector<int64_t> data = {7, 7, 7, 7, 43, 1, 1, 1, 22, 11, 425, 0, 1, 7};
//  expectedOutput.emplace("y", data);
//
//  auto output = srv.getOutput(*astOutput);
//  for (const auto &[identifier, ciphertext] : output) {
//    std::vector<int64_t> decryptedValues;
//    scf->decryptCiphertext(*ciphertext, decryptedValues);
//    std::cout << std::endl;
//    EXPECT_TRUE(expectedOutput.count(identifier) > 0);
//    auto expected = expectedOutput.at(identifier);
//    for (int i = 0; i < expected.size(); ++i) {
//      EXPECT_EQ(expected[i], decryptedValues[i]);
//    }
//}
}

#endif
