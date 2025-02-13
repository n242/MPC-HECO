
import logging

class ABCJsonAstBuilder:
    """
    Provide helper functions to create dictionary elements that correspond to ABC AST nodes when exported as JSON.
    """

    def __init__(self, log_level=logging.INFO):
        self.log_level = log_level
        logging.basicConfig(level=log_level)
        self.var_types = {}

    #
    # "Public" constants
    #
    class constants:
        LT = "<"
        GT = ">"
        LTE = "<="
        GTE = ">="
        EQ = "="
        AND = "&&"
        OR = "||"

        ADD = "+"
        SUB = "-"
        DIV = "/"
        MOD = "%"
        MUL = "*"

        SECRET_PREFIX = "secret "

    #
    # Internal helper function to create attributes for ABC nodes
    #
    def _assert_single_type_list(self, l, t):
        if any(map(lambda e: type(e) != t, l)):
            logging.error(f"Lists of mixed types are not supported. Expected all elements to be of type {t}.")
            exit(1)

    def _find_datatype(self, d):
        """
        We currently simply parse the JSON-equivalent dictionary d and then use the data type of the first literal that
        we find.

        This assumes that no type casting is supported and variables never change their type.

        :param d: JSON-equivalent dictionary of a value of which we want to find the data type.
        :return: data type "bool", "string", "char", "int", or "void"
        """
        if "type" in d and d["type"].startswith("Literal"):
            if d["type"] == "LiteralBool":
                type_name = "bool"
            elif d["type"] == "LiteralString":
                if len(d["value"]) > 1:
                    type_name = "string"
                else:
                    type_name = "char"
            elif d["type"] == "LiteralFloat":
                # Actually, in C++ we have floats and doubles. But we can't distinguish them, since their ranges overlap.
                # Thus, we just take the larger double to not lose precision.
                type_name = "double"
                logging.warning("Using double for Python float.")
            elif d["type"] == "LiteralInt":
                type_name = "int"
            else:
                type_name = "void"

            return {"type": "SimpleType", "value": type_name}
        else:
            if isinstance(d, dict):
                if d["type"] == "Variable":
                    type_name = self.var_types[d["identifier"]]
                    return type_name
                else:
                    for v in d.values():
                        type_name = self._find_datatype(v)
                        if type_name != "void":
                            return type_name
            elif isinstance(d, list):
                # By convention, an ExpressionList has the type of its elements. I.e., a list of LiteralInt is of type
                # LiteralInt too.
                return self._find_datatype(d[0])

            return {"type": "SimpleType", "value": "void"}

    def _make_abc_node(self, type, content):
        d = {"type": type}
        d.update(content)
        return d

    def _make_arguments(self, arguments):
        return {"arguments": arguments}

    def _make_body(self, body):
        return {"body": body}

    def _make_for_target(self, target):
        return {"target": target}

    def _make_for_start(self, start):
        return {"start": start}

    def _make_for_stop(self, stop):
        return {"stop": stop}

    def _make_for_step(self, step):
        return {"step": step}

    def _make_condition(self, condition):
        return {"condition": condition}

    def _make_datatype(self, val, is_secret : bool):
        type_name = self._find_datatype(val)

        # Secret types just have a prefix in the type string in JSON
        if is_secret:
            type_name = self.constants.SECRET_PREFIX + type_name

        return self._make_datatype_known(type_name)

    def _make_datatype_known(self, t):
        return {"datatype": t}

    def _make_identifier(self, identifier):
        return {"identifier": identifier}

    def _make_index(self, index):
        return {"index": index}

    def _make_initializer(self, initializer):
        return {"initializer": initializer}

    def _make_left(self, left):
        return {"left": left}

    def _make_op(self, op):
        return {"operator": op}

    def _make_params(self, params):
        return {"parameters": params}

    def _make_param_type(self, t):
        return {"parameter_type": t}

    def _make_right(self, right):
        return {"right": right}

    def _make_stmts(self, stmts):
        return {"statements": stmts}

    def _make_expressions(self, stmts):
        return {"expressions": stmts}

    def _make_return_type(self, stmt):
        return {"return_type": stmt}

    def _make_target(self, target):
        return {"target": target}

    def _make_update(self, update):
        return {"update": update}

    def _make_value(self, value):
        return {"value": value}

    def _make_then_branch(self, body):
        return {"thenBranch": body}

    def _make_else_branch(self, body):
        return {"elseBranch": body}

    #
    # "Public" functions to create ABC nodes
    #
    def make_assignment(self, target : dict, value : dict) -> dict:
        """
        Create a dictionary corresponding to an ABC assignment when exported in JSON

        :param target: target (as dict), to which the value is assigned
        :param value: value (as dict) of ABC node to assign to target
        :return: JSON-equivalent dictionary for an ABC assignment
        """

        d = self._make_target(target)
        d.update(self._make_value(value))

        # TODO: The type of target might have changed, determine and update type

        return self._make_abc_node("Assignment", d)

    def make_binary_expression(self, left : dict, op : str, right : dict) -> dict:
        """
        Create a dictionary corresponding to an ABC BinaryExpression when exported in JSON

        :param left: Expression (as dict) on the left of the operator
        :param op: Operator (as string)
        :param right: Expression (as dict) on the right of the operator
        :return: JSON-equivalent dictionary for an ABC BinaryExpression
        """

        d = self._make_left(left)
        d.update(self._make_op(op))
        d.update(self._make_right(right))

        return self._make_abc_node("BinaryExpression", d)

    def make_block(self, stmts : list) -> dict:
        """
        Create a dictionary corresponding to an ABC block containing the given statements

        :param stmts: List of JSON-equivalent dictionary ABC statement nodes
        :return: JSON-equivalent dictionary for an ABC block
        """

        return self._make_abc_node("Block", self._make_stmts(stmts))

    def make_call(self, identifier : str, arguments : list) -> dict:
        """
        Create a dictionary corresponding to an ABC Call node for the given function and arguments

        :param identifier: Name of the function
        :param arguments: List of JSON-equivalent dictionaries of ABC function parameters
        :return: JSON-equivalent dictionary for an ABC Call
        """

        d = self._make_identifier(identifier)
        d.update(self._make_arguments(arguments))

        return self._make_abc_node("Call", d)

    def make_expression_list(self, exprs : list) -> dict:
        """
        Create a dictionary corresponding to an ABC ExpressionList node when exported in JSON

        :param exprs: List of JSON-equivalent dictionaries of AbstractExpressions
        :return: JSON-equivalent dictionary for an ExpressionList node
        """

        return self._make_abc_node("ExpressionList", self._make_expressions(exprs))

    def make_function(self, identifier : str, return_type : str, params : dict, body : dict) -> dict:
        """
        Create a dictionary corresponding to an ABC Function node when exported in JSON

        :param identifier: Name of the function
        :param return_type: Return type of the function
        :param params: Parameters of the function (dict with list of FunctionParameters)
        :param body: Function body
        :return: JSON-equivalent dictionary for an Function node
        """

        d = self._make_identifier(identifier)
        d.update(self._make_return_type(return_type))
        d.update(self._make_params(params))
        d.update(self._make_body(body))

        return self._make_abc_node("Function", d)

    def make_function_param(self, identifier : str, param_type : str):
        """
        Create a dictionary corresponding to an ABC FunctionParameter node when exported in JSON

        :param identifier: Name of the parameter
        :param param_type: Type of the parameter
        :return:
        """

        d = self._make_identifier(identifier)
        d.update(self._make_param_type(param_type))

        # Save param type
        self.var_types[d["identifier"]] = d["parameter_type"]

        return self._make_abc_node("FunctionParameter", d)

    def make_for_range(self, target: dict, start: int, stop: int, step: int, body: dict) -> dict:
        d = {}
        d.update(self._make_for_target(target))
        d.update(self._make_for_start(start))
        d.update(self._make_for_stop(stop))
        d.update(self._make_for_step(step))
        d.update(self._make_body(body))
        return self._make_abc_node("ForRange", d)

    def make_for(self, initializer : dict, condition : dict, update : dict, body : dict) -> dict:
        """
        Create a dictionary corresponding to an ABC For node when exported in JSON

        :param initializer: JSON-equivalent dictionary for an ABC Block which initializes the loop variable
        :param condition: JSON-equivalent dictionary for an ABC BinaryExpression. We execute the body as long as this
                          condition is true.
        :param update: JSON-equivalent dictionary for an ABC Block that updates the loop variable
        :param body: JSON-equivalent dictionary for an ABC Block of statements that are executed in the loop
        :return: JSON-equivalent dictionary for an ABC For node
        """

        d = self._make_initializer(initializer)
        d.update(self._make_condition(condition))
        d.update(self._make_update(update))
        d.update(self._make_body(body))

        return self._make_abc_node("For", d)

    def make_if(self, condition : dict, then_branch, else_branch : dict) -> dict:
        """
        Create a dictionary corresponding to an ABC IF when exported in JSON

        :param condition: JSON-equivalent dictionary for an ABC for a BinaryExpression
        :param then_branch: JSON-equivalent dictionary for the ABC Block that is executed when the
                            condition evaluates to true.
        :param else_branch: JSON-equivalent dictionary for the ABC Block that is executed when the
                            condition evaluates to false. (optional)
        :return: JSON-equivalent dictionary for an ABC If
        """

        d = dict()
        d.update(self._make_condition(condition))
        d.update(self._make_then_branch(then_branch))

        if else_branch:
            d.update(self._make_else_branch(else_branch))

        return self._make_abc_node("If", d)

    def make_index_access(self, target : dict, index : dict):
        """
        Create a dictionary corresponding to an ABC IndexAccess node when exported in JSON

        :param target: JSON-equivalent dictionary for an ABC AbstractTarget
        :param index: JSON-equivalent dictionary for an ABC AbstractExpression
        :return: JSON-equivalent dictionary for an ABC IndexAccess node
        """

        d = self._make_target(target)
        d.update(self._make_index(index))
        return self._make_abc_node("IndexAccess", d)

    def make_literal(self, value) -> dict:
        """
        Create a dictionary corresponding to an ABC Literal* when exported in JSON, where * depends on the type of value.

        All Python floats will be translated to LiteralDouble.
        All Python strings of length <= 1 to LiteralChar.
        For other behaviour, special functions should be implemented for that purpose.

        :param value: value of the node (int, float, bool, char, string)
        :return: JSON-equivalent dictionary for an ABC Literal*
        """

        if isinstance(value, int):
            return self._make_abc_node("LiteralInt", self._make_value(value))
        elif isinstance(value, float):
            return self._make_abc_node("LiteralDouble", self._make_value(value))
        elif isinstance(value, bool):
            return self._make_abc_node("LiteralBool", self._make_value(value))
        elif isinstance(value, str):
            if len(value) > 1:
                return self._make_abc_node("LiteralString", self._make_value(value))

            return self._make_abc_node("LiteralChar", self._make_value(value))
        else:
            logging.error(f"Unsupported type '{type(value)}': only int, float, bool, and str have corresponding ABC Literals.")

    def make_return(self, value : dict) -> dict:
        """
        Create a dictionary corresponding to an ABC Return when exported in JSON

        :param value: ABC Ast node (as dictionary) to return
        :return: JSON-equivalent dictionary for an ABC Return
        """

        return self._make_abc_node("Return", self._make_value(value))

    def make_update(self, target : dict, op : str, value : dict) -> dict:
        """
        Create a dictionary corresponding to an update Block of a ABC For AST node.

        :param target: JSON-equivalent dictionary of the target variable
        :param op: arithmetic operation (represented as string, must be in self.constants)
        :param value: JSON-equivalent dictionary of the value.
        :return: JSON-equivalent of a block with the statement "target = `target` `op` `value`"
        """

        stmts = []

        update_expr = self.make_binary_expression(target, op, value)
        assignment_expr = self.make_assignment(target, update_expr)
        stmts.append(assignment_expr)

        return self.make_block(stmts)

    def make_value(self, value) -> dict:
        """
        Helper function to either create a Literal* or an ExpressionList ABC node.

        :param value: Basic python type (bool, str, int, float) or list (of such a basic type)
        :return: JSON-equivalent dictionary for either a Literal* or an ExpressionList ABC node
        """

        if isinstance(value, list):
            self._assert_single_type_list(value[1:], type(value[0]))
            return self.make_expression_list(list(map(self.make_value, value)))
        else:
            return self.make_literal(value)

    def make_variable(self, identifier : str) -> dict:
        """
        Create a dictionary corresponding to an ABC variable when exported in JSON

        :param identifier: Identifier of the variable
        :return: JSON-equivalent dictionary for an ABC variable
        """

        return self._make_abc_node("Variable", self._make_identifier(identifier))

    def make_variable_declaration(self, target : dict, value : dict, t: dict = None, is_secret : bool = False) -> dict:
        """
        Create a dictionary corresponding to an ABC variable declaration when exported in JSON

        :param target: variable (as dict), to which the value is assigned
        :param value: value (as dict) of ABC node to assign to target
        :param is_secret: Boolean set to true if the given value is secret (default: False)
        :return: JSON-equivalent dictionary for an ABC assignment
        """

        d = self._make_target(target)
        d.update(self._make_value(value))
        if t is None:
            d.update(self._make_datatype(value, is_secret))
        else:
            d.update(self._make_datatype_known(t))

        # Save resulting identifier and type
        # Here we just assume that target is always a variable (this might be problematic)
        if d["target"]["type"] == "Variable":
            self.var_types[d["target"]["identifier"]] = d["datatype"]

        return self._make_abc_node("VariableDeclaration", d)

    def make_simpletype(self, type_name: str):
        d = self._make_value(type_name)
        return self._make_abc_node("SimpleType", d)

    def make_compositetype(self, outer, inner):
        d = self._make_target(outer)
        d.update(self._make_value(inner))
        return self._make_abc_node("CompositeType", d)
