#include "../../include/ast/Function.h"

#include <utility>
#include <iostream>
#include <LiteralInt.h>
#include <BinaryExpr.h>

void Function::addParameter(const FunctionParameter &param) {
    this->params.push_back(param);
}

Function::Function(std::string name, std::vector<std::unique_ptr<AbstractStatement>> pt) : name(std::move(name)),
                                                                                           body(std::move(pt)) {
}

Function::Function(const Function &func) {
    // copy 'name'
    this->name = std::string(func.name);
    // copy 'params'
    for (const auto &p : func.params) this->params.push_back(p);
    // copy 'body'
    this->body.reserve(func.body.size());
    for (const auto &e : func.body) this->body.push_back(std::make_unique<AbstractStatement>(*e));
}

void to_json(json &j, const Function &param) {
    j = {
            {"type",   "Function"},
            {"params", param.params},
            {"body",   param.body}
    };
}

json Function::toJson() const {
//    json j;
//    to_json(j, *this);
//    return j;
    json j;
    j['type'] = "Function";
//    j["name"] = name;
//    j["params"] = params;
//    j["body"] = body;
    return j;
}

Function::Function() {

}

