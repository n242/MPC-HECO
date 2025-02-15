import ast
import logging

from ast import *

from .ABCGenericExpr import ABCGenericExpr
from .ABCJsonAstBuilder import ABCJsonAstBuilder
from .ABCTypes import is_secret, get_created_type
from .FunctionVisitor import FunctionVisitor

UNSUPPORTED_ATTRIBUTE_RESOLUTION = "Attribute resolution is not supported."
UNSUPPORTED_ONLY_ARGS = "Positional-only and keyword-only arguments are not supported."
UNSUPPORTED_STATEMENT = "Unsupported statement: '%s' is not supported."
UNSUPPORTED_SYNTAX_ERROR = "Unsupported syntax: %s."
INVALID_PYTHON_SYNTAX = "Invalid python syntax: %s."
UNSUPPORTED_MULTI_VALUE_RETURN = "Return statements with multiple values are not supported (violating line '%s')"
NO_FLOOR_DIV = "There is no type casting, division of integers will always be integer division. " \
               "Thus '/' and '//' are equivalent in ABC frontend code."
UNSUPPORTED_LOCAL_FUNCTION_CALL = "Function calls in the same context object are not yet implemented."
UNSUPPORTED_GLOBAL_FUNCTION_CALL = "Global functions calls are not yet implemented."
UNSUPPORTED_FUNCTION_ARGS = "%s are not supported! Violating function:\n%s"
BLACKBOX_FUNCTION_CALL = "Did not find source code of function call, treat it as blackbox."

class ABCVisitor(NodeVisitor):
    """
    Visitor for the Python AST, which constructs a JSON file for an ABC AST.
    """

    def __init__(self, prog, log_level=logging.INFO, *args, **kwargs):
        self.prog = prog

        self.log_level = log_level
        logging.basicConfig(level=log_level)

        self.builder = ABCJsonAstBuilder(log_level=log_level)

        # A set of variables that were already declared in the current subtree.
        # This is necessary to decide between creating an Assignment node or a VariableDeclaration.
        self.declared_vars = set()

        super(ABCVisitor, self).__init__(*args, **kwargs)

    #
    # Helper functions
    #
    def _get_composite(self, val):
        # Base case: this is a leaf object
        if isinstance(val, ast.Name):
            type_str = val.id
            created = get_created_type(type_str)
            if created is None:
                return self.builder.make_simpletype(type_str)

            sub_ast = ast.parse(f"x: {created}")
            return self._get_composite(sub_ast.body[0].annotation)

        # Recursive case: Collection with content type
        if isinstance(val, ast.Subscript):
            node = val.value
            inner = val.slice
            outer_name = "void"
            if isinstance(node, ast.Attribute):
                # Might be a fully qualified name
                outer_name = node.attr
            elif isinstance(node, ast.Name):
                outer_name = node.id
            else:
                logging.error(f"Unsupported annotation node: {node}")
                exit(1)

            return self.builder.make_compositetype(outer_name, self._get_composite(inner))

    def _get_annotation(self, arg):
        if hasattr(arg, "annotation") and arg.annotation:
            return self._get_composite(arg.annotation)
        else:
            return self.builder.make_simpletype("void")

    def _tpl_stmt_to_list(self, t):
        """
        Convert a LHS or RHS, which may be a tuple of multiple values, to a list.

        E.g., for `a, b = expr1, expr2` we have two tuples, one on the LHS with (a, b)
        and one on the RHS with (expr1, expr2).

        :param t: input, may be a tuple
        :return: list of element(s) (unpacked tuple)
        """
        if isinstance(t, Tuple):
            return list(t.elts)
        return [t]

    def _parse_lhs(self, lhs):
        """
        Parse a LHS to (supported) variables or throw an error for unsupported syntax.

        :param lhs: LHS of an assignment
        :return: a list of variables
        """

        # XXX: Currently, we do not support tuples in ABC, so we treat them differently at different
        # places. For this reason, we have a helper function instead of using visit_Name, visit_Tuple directly.
        if isinstance(lhs, Name) or isinstance(lhs, Subscript):
            return [self.visit(lhs)]
        elif isinstance(lhs, Tuple):
            return list(map(self._parse_lhs, self._tpl_stmt_to_list(lhs)))
        else:
            logging.error(
                UNSUPPORTED_SYNTAX_ERROR.format(f"type '{type(lhs)}' is not supported on the LHS of an assignment")
            )
            exit(1)

    def _args_to_dict(self, args: arguments) -> dict:
        """
        Covert a Python function argument AST node to a dictionary of the following form:
            {
                var_name = {"opt": Bool, "value": value, "secret": Bool},
                ...
            }
        where the item "opt" signals if the variable is optional and the second entry "value" stores
        the default value for optional variables (and later the real value for non-optional ones).
        "secret" stores the type hint information and is used to mark secret values.

        :param args: Python argument AST node
        :return: variable dictionary
        """

        def _make_arg_dict(secret, opt=False, val=None):
            return {"opt": opt, "value": val, "secret": secret}

        # Don't support positional only / kw only arguments
        if len(args.kwonlyargs) + len(args.posonlyargs) > 0:
            logging.error(UNSUPPORTED_ONLY_ARGS)
            exit(1)

        d = dict()
        off = len(args.args) - len(args.defaults)

        # Add arguments without default value
        for i in range(off):
            arg = args.args[i]
            annotation = self._get_annotation(arg)
            d[arg.arg] = _make_arg_dict(is_secret(annotation))

        # Add arguments with default value
        for i, default in enumerate(args.defaults):
            # Arguments with a default can never be secret.
            d[args.args[i + off].arg] = _make_arg_dict(False, True, default.value)

        return d

    def _make_assignment(self, var, expr):
        if var["type"] == "Variable":
            var_name = var["identifier"]
            if var_name in self.declared_vars:
                return self.builder.make_assignment(var, expr)
            else:
                self.declared_vars.add(var_name)
                return self.builder.make_variable_declaration(var, expr)
        else:
            # we never declare an index assignment, the indexed variable was declared before.
            return self.builder.make_assignment(var, expr)

    def _make_assignment_with_type(self, var, expr, type):
        if var["type"] == "Variable":
            var_name = var["identifier"]
            if var_name in self.declared_vars:
                return self.builder.make_assignment(var, expr)
            else:
                self.declared_vars.add(var_name)
                return self.builder.make_variable_declaration(var, expr, t=type)
        else:
            # we never declare an index assignment, the indexed variable was declared before.
            return self.builder.make_assignment(var, expr)

    def _arg_to_function_param(self, arg : arg):
        identifier = arg.arg

        # TODO: translate type annotations properly
        # type = self._get_annotation(arg)
        param_type = self._get_annotation(arg)

        return self.builder.make_function_param(identifier, param_type)

    #
    # Supported visit functions
    #

    def visit_Add(self, node: Add) -> dict:
        return self.builder.constants.ADD

    def visit_And(self, node: And) -> dict:
        return self.builder.constants.AND

    def visit_Assign(self, node: Assign) -> dict:
        """
        Visit a Python assignment and transform it to a dictionary corresponding to one or more ABC assignments.
        """

        ## First, evaluate the RHS expression
        exprs = list(map(self.visit, self._tpl_stmt_to_list(node.value)))

        ## Second, create assignments by parsing the LHS targets
        abc_assignments = []

        ### targets can be a list of variables, e.g. ["a", "b"] for "a = b = expr" syntax
        for target in node.targets:
            vars = self._parse_lhs(target)

            for var_idx, var in enumerate(vars):
                expr = exprs[var_idx]
                if isinstance(var, list):
                    if not isinstance(expr, list) or len(var) != len(expr):
                        logging.error(
                            INVALID_PYTHON_SYNTAX.format("trying to unpack more RHS values than LHS variables")
                        )
                        exit(1)

                    for i in range(len(var)):
                        abc_assignments.append(
                            self._make_assignment(var[i], expr[i])
                        )
                else:
                    abc_assignments.append(
                        self._make_assignment(var, expr)
                    )

        if len(abc_assignments) > 1:
            # XXX: This could be supported with our current AST, but would require us to build the JSON string
            # manually, so that one visit function can add more than one statement to the resulting string.
            # Alternatively, support for this can be added to the AST.
            logging.error(
                UNSUPPORTED_SYNTAX_ERROR.format(f"Multi-assignments and pattern matching are not yet supported.")
            )
            exit(1)

        return abc_assignments[0]

    def visit_AugAssign(self, node: AugAssign) -> dict:
        """
        Visit a Python augmented assignment (e.g., +=, -=, *=, ...) and transform it to a dictionary corresponding to
        an ABC assignments.
        """

        target = self.visit(node.target)
        update = self.builder.make_binary_expression(target, self.visit(node.op), self.visit(node.value))
        return self.builder.make_assignment(target, update)

    def visit_BinOp(self, node: BinOp) -> dict:
        return self.builder.make_binary_expression(
            self.visit(node.left),
            self.visit(node.op),
            self.visit(node.right)
        )

    def visit_Call(self, node: Call) -> dict:
        """
        Handle function calls, depending on where the function is located:
        - Internal functions (inside the same ABCContext) are not yet supported. In the future, they will be translated
            to AST function calls.
        - For external function calls we try to extract the expression created by them by running them at compile time
            on generic FHE objects that track the operations performed on them.
        """

        # Check if the function is defined in the same function
        if isinstance(node.func, Attribute):
            logging.error(UNSUPPORTED_ATTRIBUTE_RESOLUTION)
            exit(1)

        # Check if the function is defined on the call stack
        fn_ast = FunctionVisitor(node.func.id).visit(self.prog.src_call_stack_ast)
        if fn_ast:
            logging.error(UNSUPPORTED_LOCAL_FUNCTION_CALL)
            exit(1)
            # TODO: return here when this is implemented

        # Check if the function is defined globally in the same file
        fn_ast = FunctionVisitor(node.func.id).visit(self.prog.src_code_ast)
        if fn_ast:
            args = list(map(self.visit, node.args))
            return self.builder.make_call(node.func.id, args)

        # Check if the function is defined in the same with block
        for block in self.prog.src_curr_blocks_asts:
            fn_ast = FunctionVisitor(node.func.id).visit(block)
            if fn_ast:
                args = list(map(self.visit, node.args))
                return self.builder.make_call(node.func.id, args)

        # Otherwise, treat this function as a blackbox call. We execute the function on generic ABC values and record
        # the operations performed on those values to build an expression, with which we replace the function call.
        logging.warning(BLACKBOX_FUNCTION_CALL)

        # Create generic variables for all arguments. Turn normal arguments into AST variable nodes and recursively
        # evaluate the value of keyword arguments.
        args = [ABCGenericExpr(self.visit(arg)) for arg in node.args]
        kwargs = {keyword.arg: ABCGenericExpr(self.visit(keyword.value)) for keyword in node.keywords}

        # Get the blackbox function from the parent module and execute it on our tracing inputs.
        external_fn_ret = getattr(self.prog.src_module, node.func.id)(*args, **kwargs)

        # Return the AST expression gathered by the generic response object
        return external_fn_ret.expr

    def visit_Compare(self, node: Compare) -> dict:
        """
        Visit a Python compare and transform it to a dictionary corresponding to an ABC BinaryExpression.
        """
        # TODO: we don't support multiple operands (e.g. 0 <= x < 10). A compare is treated like a
        #  normal condition
        if len(node.ops) > 1 or len(node.comparators) > 1:
            logging.error(UNSUPPORTED_SYNTAX_ERROR,
                          f"Compare operations with multiple operands are not supported: {node.ops}")
            exit(1)

        return self.builder.make_binary_expression(
            self.visit(node.left),
            self.visit(node.ops[0]),
            self.visit(node.comparators[0]),
        )

    def visit_Constant(self, node: Constant):
        """
        Visit a Python constant and transform it to a dictionary corresponding to an ABC literal.
        """

        return self.builder.make_literal(node.value)

    def visit_Div(self, node: Div) -> dict:
        return self.builder.constants.DIV

    def visit_Eq(self, node: Eq) -> dict:
        return self.builder.constants.EQ

    def visit_FloorDiv(self, node: FloorDiv) -> dict:
        logging.warning(NO_FLOOR_DIV);
        return self.builder.constants.DIV

    def visit_For(self, node: For) -> dict:
        """
        Visit a Python For node and convert it to an ABC AST For node.
        """

        target = self.visit(node.target)

        # Currently only support iterating over range!
        if node.iter.func.id != "range":
            logging.error("The python frontend currently only supports iterating over a `range`")
            exit(1)
        elif len(node.orelse) != 0:
            logging.error("Orelse construct of for loops is not supported.")
            exit(1)

        # case range(stop) -> [0, stop)
        if len(node.iter.args) == 1:
            start_val = self.builder.make_literal(0)
            stop_val = self.visit(node.iter.args[0])
        # cases range(start, stop[, step]) -> [start, stop)
        else:
            start_val = self.visit(node.iter.args[0])
            stop_val = self.visit(node.iter.args[1])

        # case range(start, stop, step)
        if len(node.iter.args) == 3:
            step_val = self.visit(node.iter.args[2])
        else:
            step_val = self.builder.make_literal(1)

        stmts = list(map(self.visit, node.body))
        body = self.builder.make_block(stmts)

        # If step_val is a literal node with value of 1 we change it to 1
        if "type" in step_val and step_val["type"] == "LiteralInt" and step_val["value"] == 1:
            step_val = 1

        if step_val == 1:
            return self.builder.make_for_range(target, start_val, stop_val, step_val, body)

        # Currently, the initializer is a block with a single statement.
        var_decl = self.builder.make_variable_declaration(target, start_val)

        # TODO: We force set the type of the for-loop variable to integer. This is not automatically the case, since
        # variable assignments loose type information (see frontend-limitations markdown).
        var_decl["datatype"] = "int"

        initializer = self.builder.make_block([var_decl])

        # Python for loops with range only perform addition, the Pythonic way to do more complex conditions is usually
        # to use while loops.
        update = self.builder.make_update(target, self.builder.constants.ADD, step_val)

        # If start > stop, the condition is target > stop. Otherwise, it is target < stop.
        start_lte_stop = self.builder.make_binary_expression(start_val, self.builder.constants.LTE, stop_val)
        start_gt_stop = self.builder.make_binary_expression(start_val, self.builder.constants.GT, stop_val)
        target_lt_stop = self.builder.make_binary_expression(target, self.builder.constants.LT, stop_val)
        target_gt_stop = self.builder.make_binary_expression(target, self.builder.constants.GT, stop_val)

        condition_case_1 = self.builder.make_binary_expression(start_lte_stop, self.builder.constants.AND,
                                                               target_lt_stop)
        condition_case_2 = self.builder.make_binary_expression(start_gt_stop, self.builder.constants.AND,
                                                               target_gt_stop)
        condition = self.builder.make_binary_expression(condition_case_1, self.builder.constants.OR, condition_case_2)

        return self.builder.make_for(initializer, condition, update, body)

    def visit_FunctionDef(self, node: FunctionDef) -> dict:
        """
        Visit a Python function definition and convert it to an AST function definition.
        """

        # logging.debug(f"Parsing python function:\n{unparse(node)}")

        last_stmt = node.body[-1]
        if not isinstance(last_stmt, Return):
            logging.warning("Function without return statement found.")

        # Parse the return type
        # TODO [mh]: as an addition, we could parse "returns" return type annotations
        if isinstance(node.returns, ast.Subscript) or isinstance(node.returns, ast.Name):
            return_type = self._get_composite(node.returns)
        else:
            return_type = self.builder.make_simpletype("void")

        # Parse the function arguments
        if len(node.args.kwonlyargs) > 0:
            logging.error(UNSUPPORTED_FUNCTION_ARGS.format("kwonlyargs", unparse(node)))
            exit(1)
        if len(node.args.posonlyargs) > 0:
            logging.error(UNSUPPORTED_FUNCTION_ARGS.format("posonlyargs", unparse(node)))
            exit(1)
        if len(node.args.kw_defaults) > 0:
            logging.error(UNSUPPORTED_FUNCTION_ARGS.format("kw_defaults", unparse(node)))
            exit(1)
        if len(node.args.defaults) > 0:
            logging.error(UNSUPPORTED_FUNCTION_ARGS.format("defaults", unparse(node)))
            exit(1)

        params = list(map(self._arg_to_function_param, node.args.args))

        # Parse the function body
        stmts = list(map(self.visit, node.body))
        body = self.builder.make_block(stmts)

        # TODO: nested functions (function definitions inside other functions) are neither detected nor supported.
        fn = self.builder.make_function(node.name, return_type, params, body)
        self.prog.add_fn(fn)

        return fn

    def visit_Gt(self, node: Gt) -> dict:
        return self.builder.constants.GT

    def visit_GtE(self, node: GtE) -> dict:
        return self.builder.constants.GTE

    def visit_If(self, node: If) -> dict:
        """
        Visit a Python If node and transform it to a dictionary corresponding to an ABC If.
        """

        # Parse if branch
        stmts = list(map(self.visit, node.body))
        if_branch = self.builder.make_block(stmts)

        # Parse else branch
        if len(node.orelse) > 0:
            stmts = list(map(self.visit, node.orelse))
            else_branch = self.builder.make_block(stmts)
        else:
            else_branch = None

        return self.builder.make_if(
            self.visit(node.test),
            if_branch,
            else_branch
        )

    def visit_Index(self, node: Index) -> dict:
        # TODO: so far, all Index nodes that we used only had the single attribute "value"
        return self.visit(node.value)

    def visit_List(self, node: List) -> dict:
        """
        Visit a Python list and convert it to an AST ExpressionList.
        """
        # TODO: at the moment, python lists are translated to ABC ExpressionLists. We potentially need to give up some
        #   list features if we keep it like this (list comprehension, list concatenation).

        exprs = list(map(self.visit, node.elts))
        return self.builder.make_expression_list(exprs)

    def visit_Lt(self, node: Lt) -> dict:
        return self.builder.constants.LT

    def visit_LtE(self, node: LtE) -> dict:
        return self.builder.constants.LTE

    def visit_Mod(self, node: Mod) -> dict:
        return self.builder.constants.MOD

    def visit_Mult(self, node: Mult) -> dict:
        return self.builder.constants.MUL

    def visit_Name(self, node: Name) -> dict:
        """
        Visit a Python name node and convert it to an ABC AST Variable node.
        """

        return self.builder.make_variable(node.id)

    def visit_Num(self, node: Num) -> dict:
        """
        Visit a Python Num and transform it to a dictionary corresponding to an ABC literal.
        (deprecated after Python 3.6, here for backwards compatibility)
        """

        return self.builder.make_literal(node.n)

    def visit_Or(self, node: Or) -> dict:
        return self.builder.constants.OR

    def visit_Return(self, node: Return) -> dict:
        """
        Visit a Python return statement, convert its value to an ABC node and return an ABC Return node.
        """

        # Only support single return statements, since we don't support multi-value return statements yet
        if isinstance(node.value, Tuple):
            logging.error(UNSUPPORTED_MULTI_VALUE_RETURN, unparse(node))
            exit(1)

        ret_node = self.visit(node.value)

        return self.builder.make_return(ret_node)

    def visit_Sub(self, node: Sub) -> dict:
        return self.builder.constants.SUB

    def visit_Subscript(self, node: Subscript) -> dict:
        target = self.visit(node.value)

        # Slice accesses will throw an error, since the Slice type is not implemented.
        index = self.visit(node.slice)

        return self.builder.make_index_access(target, index)

    #
    # Unsupported visit functions
    #

    def visit_Assert(self, node: Assert) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Attribute(self, node: Attribute) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Await(self, node: Await) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_AnnAssign(self, node: AnnAssign) -> dict:
        # First, evaluate the RHS expression
        exp = self.visit(node.value)

        # Get the target
        target = self._parse_lhs(node.target)[0]

        # Get type
        type_ann = self._get_annotation(node)

        return self._make_assignment_with_type(target, exp, type_ann)

    def visit_AsyncFor(self, node: AsyncFor) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_AsyncWith(self, node: AsyncWith) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_AugLoad(self, node: AugLoad) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_AugStore(self, node: AugStore) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_BoolOp(self, node: BoolOp) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_BitAnd(self, node: BitAnd) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_BitOr(self, node: BitOr) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_BitXor(self, node: BitXor) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Break(self, node: Break) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Bytes(self, node: Bytes) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_ClassDef(self, node: ClassDef) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Continue(self, node: Continue) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Del(self, node: Del) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Delete(self, node: Delete) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Dict(self, node: Dict) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_DictComp(self, node: DictComp) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Ellipsis(self, node: Ellipsis) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_ExceptHandler(self, node: ExceptHandler) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Expr(self, node: Expr) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Expression(self, node: Expression) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_ExtSlice(self, node: ExtSlice) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_FormattedValue(self, node: FormattedValue) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_GeneratorExp(self, node: GeneratorExp) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Global(self, node: Global) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_IfExp(self, node: IfExp) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Import(self, node: Import) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_ImportFrom(self, node: ImportFrom) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_In(self, node: In) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Interactive(self, node: Interactive) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Invert(self, node: Invert) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Is(self, node: Is) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_IsNot(self, node: IsNot) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_JoinedStr(self, node: JoinedStr) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Lambda(self, node: Lambda) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_ListComp(self, node: ListComp) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Load(self, node: Load) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_LShift(self, node: LShift) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_MatMult(self, node: MatMult) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Module(self, node: Module) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_NameConstant(self, node: NameConstant) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    #def visit_NamedExpr(self, node: NamedExpr) -> dict:
    #    logging.error(UNSUPPORTED_STATEMENT, type(node))
    #    exit(1)

    def visit_Nonlocal(self, node: Nonlocal) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Not(self, node: Not) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_NotEq(self, node: NotEq) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_NotIn(self, node: NotIn) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Param(self, node: Param) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Pass(self, node: Pass) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Pow(self, node: Pow) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Raise(self, node: Raise) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_RShift(self, node: RShift) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Set(self, node: Set) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_SetComp(self, node: SetComp) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Slice(self, node: Slice) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Starred(self, node: Starred) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Store(self, node: Store) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Str(self, node: Str) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Suite(self, node: Suite) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Try(self, node: Try) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Tuple(self, node: Tuple) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_UAdd(self, node: UAdd) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_UnaryOp(self, node: UnaryOp) -> dict:
        if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
            # This is a negative constant
            return self.builder.make_literal(-node.operand.value)

        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_USub(self, node: USub) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_While(self, node: While) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_With(self, node: With) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_Yield(self, node: Yield) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)

    def visit_YieldFrom(self, node: YieldFrom) -> dict:
        logging.error(UNSUPPORTED_STATEMENT, type(node))
        exit(1)
