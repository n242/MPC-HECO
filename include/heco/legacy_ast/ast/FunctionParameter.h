#ifndef AST_OPTIMIZER_INCLUDE_AST_OPT_AST_FUNCTION_PARAMETER_H_
#define AST_OPTIMIZER_INCLUDE_AST_OPT_AST_FUNCTION_PARAMETER_H_

#include <map>
#include <string>
#include <vector>
#include "heco/legacy_ast/ast/AbstractTarget.h"
#include "heco/legacy_ast/ast_utilities/Datatype.h"

/// typed parameters defined as inputs for a function
class FunctionParameter : public AbstractTarget
{
private:
    /// Name of this FunctionParameter
    std::string identifier;

    /// Type of this FunctionParameter
    Datatype parameter_type;

    /// Creates a deep copy of the current node
    /// Should be used only by Nodes' clone()
    /// \return a copy of the current node
    FunctionParameter *clone_impl(AbstractNode *parent) const override;

public:
    /// Destructor
    ~FunctionParameter() override;

    /// Create a FunctionParameter with name identifier
    /// \param identifier FunctionParameter name, can be any valid string
    explicit FunctionParameter(Datatype parameter_type, std::string identifier);

    /// Copy constructor
    /// \param other FunctionParameter to copy
    FunctionParameter(const FunctionParameter &other);

    /// Move constructor
    /// \param other FunctionParameter to copy
    FunctionParameter(FunctionParameter &&other) noexcept;

    /// Copy assignment
    /// \param other FunctionParameter to copy
    /// \return This object
    FunctionParameter &operator=(const FunctionParameter &other);

    /// Move assignment
    /// \param other FunctionParameter to move
    /// \return This object
    FunctionParameter &operator=(FunctionParameter &&other) noexcept;

    /// Deep copy of the current node
    /// \return A deep copy of the current node
    std::unique_ptr<FunctionParameter> clone(AbstractNode *parent = nullptr) const;

    [[nodiscard]] std::string getIdentifier() const;

    Datatype &getParameterType();

    [[nodiscard]] const Datatype &getParameterType() const;

    /// Create a FunctionParameter node from a nlohmann::json representation of this node.
    /// \return unique_ptr to a new For node
    static std::unique_ptr<FunctionParameter> fromJson(nlohmann::json j);

    ///////////////////////////////////////////////
    ////////// AbstractNode Interface /////////////
    ///////////////////////////////////////////////
    void accept(IVisitor &v) override;

    iterator begin() override;

    const_iterator begin() const override;

    iterator end() override;

    const_iterator end() const override;

    size_t countChildren() const override;

    nlohmann::json toJson() const override;

    std::string toString(bool printChildren) const override;

protected:
    std::string getNodeType() const override;
};

#endif // AST_OPTIMIZER_INCLUDE_AST_OPT_AST_FUNCTION_PARAMETER_H_
