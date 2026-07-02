import ast
import os
import sys

class LeakageNodeVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.violations = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            
            # 1. Detect .shift(-N)
            if func_name == 'shift':
                for arg in node.args:
                    # Check if arg is a unary operation (like -1)
                    if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                        self.violations.append(f"Line {node.lineno}: DETECTED .shift(-X) lookahead bias.")
            
            # 2. Detect .rolling(center=True)
            if func_name == 'rolling':
                for kw in node.keywords:
                    if kw.arg == 'center':
                        if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            self.violations.append(f"Line {node.lineno}: DETECTED .rolling(center=True) lookahead bias.")
                        elif isinstance(kw.value, ast.NameConstant) and kw.value.value is True: # Python 3.7 and older
                            self.violations.append(f"Line {node.lineno}: DETECTED .rolling(center=True) lookahead bias.")

        self.generic_visit(node)

    def visit_Subscript(self, node):
        # 3. Detect rudimentary future indexing via iloc [i+1]
        # This is a heuristic. It looks for df.iloc[i+1] or similar operations inside a slice or index.
        if isinstance(node.value, ast.Attribute) and node.value.attr == 'iloc':
            # Check the slice
            if isinstance(node.slice, ast.BinOp):
                if isinstance(node.slice.op, ast.Add):
                    # Check if it looks like i+1 or i+X where X > 0
                    if isinstance(node.slice.right, ast.Constant) and isinstance(node.slice.right.value, int) and node.slice.right.value > 0:
                        self.violations.append(f"Line {node.lineno}: DETECTED potential future indexing via iloc[+X].")
            elif hasattr(ast, 'Index') and isinstance(node.slice, ast.Index): # Python 3.8 and older
                if isinstance(node.slice.value, ast.BinOp) and isinstance(node.slice.value.op, ast.Add):
                    if isinstance(node.slice.value.right, ast.Constant) and isinstance(node.slice.value.right.value, int) and node.slice.value.right.value > 0:
                        self.violations.append(f"Line {node.lineno}: DETECTED potential future indexing via iloc[+X].")

        self.generic_visit(node)

def analyze_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        print(f"Could not read {filepath}: {e}")
        return []

    try:
        tree = ast.parse(source)
    except Exception as e:
        print(f"Syntax error in {filepath}: {e}")
        return []

    visitor = LeakageNodeVisitor(filepath)
    visitor.visit(tree)
    return visitor.violations

def main():
    target_dirs = ['strategy', 'ml', 'data', 'market']
    all_violations = {}

    for d in target_dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    violations = analyze_file(filepath)
                    if violations:
                        all_violations[filepath] = violations

    if all_violations:
        print("\n" + "="*50)
        print("! LEAKAGE DETECTED !")
        print("="*50)
        for filepath, violations in all_violations.items():
            print(f"\nFile: {filepath}")
            for v in violations:
                print(f"  - {v}")
        print("\nPIPELINE STOPPED. Strategy invalid until leakage is fixed.")
        sys.exit(1)
    else:
        print("OK: Leakage Firewall Passed. No explicit future-peeking detected.")

if __name__ == "__main__":
    main()
