#ifndef AST_OPTIMIZER_INCLUDE_AST_OPT_PARSER_FILE_H_
#define AST_OPTIMIZER_INCLUDE_AST_OPT_PARSER_FILE_H_

#include <string>
#include "heco/legacy_ast/ast_parser/Errors.h"

namespace stork
{

    class File
    {
    private:
        FILE *_fp;

    public:
        explicit File(const char *path);

        ~File();

        int operator()();

        File(const File &) = delete;

        void operator=(const File &) = delete;
    };
} // namespace stork
#endif // AST_OPTIMIZER_INCLUDE_AST_OPT_PARSER_FILE_H_
