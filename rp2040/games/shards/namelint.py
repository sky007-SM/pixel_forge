"""Find names that are used but never defined (typos / missing imports) and imports MicroPython lacks."""
import ast, symtable, sys, glob, builtins
OK_MODS = {"math","array","sys","gc","uctypes","micropython","time","random","io","os","json","machine","rp2"}
bad = 0
for fn in sorted(glob.glob(sys.argv[1] + "/*.py")):
    src = open(fn).read()
    tree = ast.parse(src)
    defined = set(dir(builtins)) | {"ptr8","ptr16","ptr32","__name__"}
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: defined.add((a.asname or a.name).split(".")[0])
            mod = (n.module if isinstance(n, ast.ImportFrom) else n.names[0].name) or ""
            top = mod.split(".")[0]
            if top and top not in OK_MODS and top not in ("hardware","system","assets","games","config"):
                print(fn, "unknown module", mod); bad += 1
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)): defined.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name): defined.add(x.id)
    # names assigned via 'global X' inside functions count as defined
    for n in ast.walk(tree):
        if isinstance(n, ast.Global): defined.update(n.names)
    def walk(t):
        global bad
        for s in t.get_symbols():
            if s.is_global() and s.is_referenced() and s.get_name() not in defined:
                print("%s: undefined global %r in %s" % (fn, s.get_name(), t.get_name())); bad += 1
        for c in t.get_children(): walk(c)
    walk(symtable.symtable(src, fn, "exec"))
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr): print(fn, n.lineno, "f-string"); bad += 1
        if isinstance(n, (ast.Import, ast.ImportFrom)) and n not in tree.body:
            mod = (n.module if isinstance(n, ast.ImportFrom) else n.names[0].name) or ""
print("name lint:", "OK" if not bad else "%d problem(s)" % bad)
