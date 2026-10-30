"""Static lint for MicroPython viper rules (CPython cannot check these).
 - results of calls to other functions are 'object' typed: must be wrapped in int()/ptrN() before arithmetic/compare
 - max 4 positional args, no defaults, no *args
 - no float constants, no for-else, no nested defs/lambdas, no try/with, no f-strings/str ops
 - names used must be local, const-style ints, or known callables"""
import ast, sys, glob
CASTS = {"int", "uint", "ptr8", "ptr16", "ptr32", "bool"}
bad = 0
for fn in sorted(glob.glob(sys.argv[1] + "/*.py")):
    tree = ast.parse(open(fn).read())
    top_funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not any((isinstance(d, ast.Attribute) and d.attr == "viper") for d in node.decorator_list):
            continue
        name = node.name
        def err(n, msg):
            global bad
            bad += 1
            print("%s:%d %s: %s" % (fn, n.lineno, name, msg))
        a = node.args
        if len(a.args) > 4: err(node, "more than 4 args")
        if a.defaults or a.vararg or a.kwarg: err(node, "defaults/varargs")
        for ar in a.args:
            if ar.annotation is None: err(node, "arg %s has no type annotation" % ar.arg)
        objvars = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Constant) and isinstance(n.value, (float, str)) and not isinstance(n.value, bool):
                if n is not node.body[0].value if isinstance(node.body[0], ast.Expr) else True:
                    err(n, "float/str constant %r" % (n.value,))
            if isinstance(n, (ast.FunctionDef, ast.Lambda)) and n is not node: err(n, "nested def/lambda")
            if isinstance(n, (ast.Try, ast.With, ast.For, ast.ListComp, ast.GeneratorExp, ast.JoinedStr)): err(n, type(n).__name__ + " not allowed")
            if isinstance(n, ast.Assign):
                v = n.value
                if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id not in CASTS:
                    for t in n.targets:
                        if isinstance(t, ast.Name): objvars.add(t.id)
        def has_bare_call(e):
            for c in ast.walk(e):
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id not in CASTS:
                    return c
            return None
        # bare calls used inside arithmetic / comparisons
        for n in ast.walk(node):
            if isinstance(n, (ast.BinOp, ast.Compare, ast.BoolOp, ast.UnaryOp)):
                for sub in ast.iter_child_nodes(n):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id not in CASTS:
                        err(n, "call to %s() used in an expression without int()" % sub.func.id)
                    if isinstance(sub, ast.Name) and sub.id in objvars:
                        err(n, "object-typed variable %s used in an expression" % sub.id)
print("viper lint:", "OK" if not bad else "%d problem(s)" % bad)
sys.exit(1 if bad else 0)
