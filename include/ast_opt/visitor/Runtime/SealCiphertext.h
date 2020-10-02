#ifndef GRAPHNODE_H_INCLUDE_AST_OPT_VISITOR_RUNTIME_SEALCIPHERTEXT_H_
#define GRAPHNODE_H_INCLUDE_AST_OPT_VISITOR_RUNTIME_SEALCIPHERTEXT_H_

#include <memory>
#include "AbstractCiphertext.h"

// forward declarations
class SealCiphertextFactory;

#ifdef HAVE_SEAL_BFV
#include <seal/seal.h>

class SealCiphertext : public AbstractCiphertext {
 private:
  /// The encrypted data in this ciphertext wrapper.
  seal::Ciphertext ciphertext;

  /// A reference to the factory that created this ciphertext.
  SealCiphertextFactory &factory;

 public:
  ~SealCiphertext() override = default;

  /// Creates a new SealCiphertext: a wrapper around the seal::Ciphertext class.
  /// \param sealFactory The factory that created this ciphertext.
  explicit SealCiphertext(SealCiphertextFactory &sealFactory);

  /// Gets the seal::Ciphertext associated with this SealCiphertext.
  /// \return (A const reference) to the underlying seal::Ciphertext.
  [[nodiscard]] const seal::Ciphertext &getCiphertext() const;

  /// Gets the seal::Ciphertext associated with this SealCiphertext.
  /// \return (A reference) to the underlying seal::Ciphertext.
  seal::Ciphertext &getCiphertext();

  std::unique_ptr<AbstractCiphertext> multiply(AbstractCiphertext &operand) override;

  void multiplyInplace(AbstractCiphertext &operand) override;

  std::unique_ptr<AbstractCiphertext> add(AbstractCiphertext &operand) override;

  void addInplace(AbstractCiphertext &operand) override;

  std::unique_ptr<AbstractCiphertext> subtract(AbstractCiphertext &operand) override;

  void subtractInplace(AbstractCiphertext &operand) override;

  std::unique_ptr<AbstractCiphertext> rotateRows(int steps) override;

  void rotateRowsInplace(AbstractCiphertext &abstractCiphertext, int steps) override;
};

#endif
#endif //GRAPHNODE_H_INCLUDE_AST_OPT_VISITOR_RUNTIME_SEALCIPHERTEXT_H_
